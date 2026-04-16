import streamlit as st
import os, shutil, pandas as pd, requests
from datetime import datetime
from sqlalchemy import func

# --- IMPORTS INTERNES ---
from database import SessionLocal, Account, Record, Position, UserProfile
from auth import get_user_info
from parser import check_quota_and_parse
from modules.charts import render_patrimoine_chart, render_account_history, render_allocation_chart
from modules.notifications import send_discord_msg
from fix_db import migrate

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Aura Wealth Pro", page_icon="🌌", layout="wide", initial_sidebar_state="expanded")

def safe_float(value):
    try:
        if value is None or value == "": return 0.0
        if isinstance(value, str):
            value = value.replace('€', '').replace(' ', '').replace(',', '.')
        return float(value)
    except: return 0.0

def manage_token_resets(profile, db):
    today = datetime.now().date()
    current_week = today.isocalendar()[1]
    updated = False
    if profile.last_daily_reset != today:
        profile.token_used_daily = 0
        profile.last_daily_reset = today
        updated = True
    if profile.last_weekly_reset != current_week:
        profile.token_used_weekly = 0
        profile.last_weekly_reset = current_week
        updated = True
    if updated: db.commit()

@st.cache_data(ttl=3600, show_spinner=False)
def get_exchange_rates():
    try: return requests.get("https://open.er-api.com/v6/latest/EUR", timeout=3).json().get("rates", {"EUR": 1.0, "CHF": 0.98, "USD": 1.08})
    except: return {"EUR": 1.0, "CHF": 0.98, "USD": 1.08}

rates = get_exchange_rates()
def convert_to_eur(amount, currency):
    if currency == "EUR" or not currency: return amount
    rate = rates.get(currency.upper(), 1.0)
    return amount / rate if rate > 0 else amount

def get_multi_currency_caption(amount_eur, active_currencies):
    """Génère la chaîne de caractères pour les devises secondaires (ex: ≈ 980 CHF / ≈ 1080 USD)"""
    currs = [c.strip() for c in active_currencies.split(",") if c.strip() and c.strip() != "EUR"]
    if not currs: return ""
    res = []
    for c in currs:
        rate = rates.get(c, 1.0)
        res.append(f"≈ {amount_eur * rate:,.0f} {c}")
    return " | ".join(res)

# --- INITIALISATION DB ---
try: migrate() 
except: pass

db = SessionLocal()

try:
    user = get_user_info()
    if not user or not user.get("username"): 
        st.warning("Veuillez vous connecter.")
        st.stop()

    profile = db.query(UserProfile).filter_by(username=user["username"]).first()
    if not profile:
        profile = UserProfile(username=user["username"], last_daily_reset=datetime.now().date(), last_weekly_reset=datetime.now().date().isocalendar()[1])
        db.add(profile); db.commit(); db.refresh(profile)

    manage_token_resets(profile, db)

    # --- SIDEBAR ---
    with st.sidebar:
        st.title("🌌 Aura Pro")
        st.write(f"Utilisateur : **{user['username']}**")
        menu = st.radio("Navigation", ["🌍 Dashboard", "💳 Mes Comptes", "📑 Export", "⚙️ Paramètres", "🛡️ Admin"] if user["is_admin"] else ["🌍 Dashboard", "💳 Mes Comptes", "📑 Export", "⚙️ Paramètres"])
        
        st.divider()
        st.subheader("📅 Quota IA Hebdomadaire")
        u_pct = (profile.token_used_weekly / profile.token_limit_weekly) if profile.token_limit_weekly > 0 else 0
        st.progress(min(max(u_pct, 0.0), 1.0), text=f"{profile.token_used_weekly:,} / {profile.token_limit_weekly:,}")

    # --- PAGE : DASHBOARD ---
    if menu == "🌍 Dashboard":
        st.header("📈 Dashboard Patrimonial")
        accounts = db.query(Account).filter_by(user_id=user["username"]).all()
        
        if not accounts:
            st.info("👋 Bienvenue ! Ajoutez vos premiers comptes (Livrets ou PDF) dans l'onglet **Mes Comptes**.")
        else:
            total_inv_eur, total_val_eur, total_euro_eur, total_uc_eur, total_div_eur = 0, 0, 0, 0, 0
            perf_summary, all_positions = [], []

            for a in accounts:
                last_r = db.query(Record).filter_by(account_id=a.id).order_by(Record.date_releve.desc()).first()
                if last_r:
                    total_inv_eur += convert_to_eur(last_r.total_invested or 0, a.currency)
                    total_val_eur += convert_to_eur(last_r.total_value or 0, a.currency)
                    
                    euro_val = (last_r.total_value or 0) if a.is_manual else (last_r.fonds_euro_value or 0)
                    total_euro_eur += convert_to_eur(euro_val, a.currency)
                    total_uc_eur += convert_to_eur(last_r.uc_value or 0, a.currency)
                    total_div_eur += convert_to_eur(sum(r.dividends for r in a.records if r.dividends), a.currency)
                    
                    inv_natif = last_r.total_invested or 0
                    gain_natif = last_r.total_value - inv_natif
                    pct = (gain_natif / inv_natif * 100) if inv_natif > 0 else 0
                    
                    type_display = f"{a.account_type} ✍️" if a.is_manual else a.account_type
                    val_str = f"{last_r.total_value:,.2f} {a.currency}"
                    if a.currency != "EUR": val_str += f" (~{convert_to_eur(last_r.total_value, a.currency):,.0f} €)"
                    
                    perf_summary.append({
                        "Compte": a.bank_name, "Type": type_display, "Capital": f"{inv_natif:,.2f} {a.currency}",
                        "Valeur": val_str, "Plus-Value": f"{gain_natif:+.2f} {a.currency}", "Perf.": f"{pct:+.2f}%"
                    })
                    
                    for pos in last_r.positions:
                        all_positions.append({"Compte": a.bank_name, "Actif": pos.name, "Type": pos.asset_type, "Quantité": pos.quantity, "Valeur": f"{pos.total_value:,.2f} {a.currency}"})

            # AFFICHAGE DES KPIS AVEC CONVERSION MULTI-DEVISES
            k1, k2, k3, k4 = st.columns(4)
            
            k1.metric("Capital Versé Global", f"{total_inv_eur:,.0f} €")
            if sub_inv := get_multi_currency_caption(total_inv_eur, profile.active_currencies):
                k1.caption(sub_inv)
                
            k2.metric("Valeur Marché Globale", f"{total_val_eur:,.2f} €")
            if sub_val := get_multi_currency_caption(total_val_eur, profile.active_currencies):
                k2.caption(sub_val)
                
            gain_tot = total_val_eur - total_inv_eur
            k3.metric("Plus-Value Nette", f"{gain_tot:+.2f} €", f"{(gain_tot/total_inv_eur*100):+.2f}%" if total_inv_eur > 0 else "0%")
            if sub_gain := get_multi_currency_caption(gain_tot, profile.active_currencies):
                k3.caption(sub_gain)
                
            k4.metric("Primes / Dividendes", f"{total_div_eur:,.2f} €")
            if sub_div := get_multi_currency_caption(total_div_eur, profile.active_currencies):
                k4.caption(sub_div)

            st.divider()
            c_l, c_r = st.columns(2)
            with c_l: render_patrimoine_chart(accounts)
            with c_r: render_allocation_chart(total_euro_eur, total_uc_eur)
            
            st.subheader("📋 Résumé des Portefeuilles")
            st.dataframe(pd.DataFrame(perf_summary), hide_index=True, use_container_width=True)
            
            if all_positions:
                st.subheader("🔍 Détail des Actifs (ETF, Fonds, Actions)")
                st.dataframe(pd.DataFrame(all_positions), hide_index=True, use_container_width=True)

    # --- PAGE : MES COMPTES ---
    elif menu == "💳 Mes Comptes":
        st.header("💳 Gestion & Ajout de comptes")
        
        tab_import, tab_manual, tab_manage = st.tabs(["📥 Import PDF (IA)", "✍️ Saisie Manuelle (Livrets)", "📂 Gérer mes comptes"])
        
        # ONGLET IMPORT IA
        with tab_import:
            st.info("Glissez votre relevé PDF (Assurance Vie, PEA, Amundi, Natixis...).")
            up_file = st.file_uploader("Fichier PDF", type="pdf", label_visibility="collapsed")
            
            if up_file:
                file_key = f"pdf_{up_file.file_id}"
                
                if file_key not in st.session_state and f"done_{file_key}" not in st.session_state:
                    with st.status("🔮 L'IA lit votre document en profondeur...", expanded=True) as status:
                        t_path = f"/tmp/{up_file.file_id}.pdf"
                        
                        with open(t_path, "wb") as f:
                            f.write(up_file.getvalue())
                            
                        res = check_quota_and_parse(t_path, os.getenv("GEMINI_API_KEY"))
                        
                        if "error" in res:
                            st.error(res["error"])
                            status.update(label="❌ Erreur d'analyse", state="error")
                        else:
                            st.session_state[file_key] = res
                            st.session_state[f"path_{file_key}"] = t_path
                            status.update(label="✅ Analyse terminée !", state="complete")
                            db.close()
                            st.rerun()

                elif isinstance(st.session_state.get(file_key), dict):
                    res = st.session_state[file_key]
                    
                    with st.form(key=f"form_{file_key}", border=True):
                        st.markdown("### 📋 Validation et Corrections")
                        st.info("💡 L'IA a extrait ces montants. Vous pouvez les corriger avant de sauvegarder.")
                        
                        c1, c2, c3 = st.columns(3)
                        e_bank = c1.text_input("Banque", value=res.get("bank_name", ""))
                        e_date = c2.text_input("Date (YYYY-MM-DD)", value=res.get("date", ""))
                        c_list = ["EUR", "CHF", "USD", "GBP", "CAD"]
                        e_curr = c3.selectbox("Devise", options=c_list, index=c_list.index(res.get("currency", "EUR")) if res.get("currency", "EUR") in c_list else 0)
                        
                        c4, c5, c6 = st.columns(3)
                        e_val = c4.number_input("Valeur Totale", value=safe_float(res.get("total_value")), step=10.0)
                        e_inv = c5.number_input("Capital Versé (ou Versements)", value=safe_float(res.get("total_invested")), step=10.0)
                        e_type = c6.text_input("Type de compte", value=res.get("account_type", ""))
                        
                        e_div = st.number_input("Primes / Dividendes / Intéressement détectés", value=safe_float(res.get("dividends")), step=10.0)
                        
                        with st.expander("Voir le détail brut des actifs détectés"):
                            st.json(res.get("positions", []))
                        
                        existing = db.query(Account).filter_by(user_id=user["username"]).all()
                        opts = {f"{a.bank_name} - {a.account_type} (N°{a.contract_number})": a.id for a in existing if not a.is_manual}
                        opts["➕ Créer un nouveau compte PDF"] = "NEW"
                        target = st.selectbox("Assigner ce relevé à :", options=opts.keys())
                        
                        if st.form_submit_button("💾 Sauvegarder dans mon patrimoine", type="primary"):
                            try:
                                acc_id = opts[target]
                                try: p_date = datetime.strptime(e_date, "%Y-%m-%d").date()
                                except: p_date = datetime.now().date()

                                if acc_id == "NEW":
                                    new_a = Account(user_id=user["username"], bank_name=e_bank, account_type=e_type, contract_number=res.get("contract_number"), currency=e_curr, total_invested=e_inv, is_manual=False)
                                    db.add(new_a); db.commit(); db.refresh(new_a); acc_id = new_a.id
                                else:
                                    a_obj = db.get(Account, acc_id)
                                    a_obj.total_invested = e_inv

                                new_r = Record(account_id=acc_id, date_releve=p_date, total_value=e_val, total_invested=e_inv, fonds_euro_value=safe_float(res.get("fonds_euro_value")), uc_value=safe_float(res.get("uc_value")), dividends=e_div)
                                db.add(new_r); db.commit(); db.refresh(new_r)
                                
                                for pos in res.get("positions", []):
                                    new_pos = Position(
                                        record_id=new_r.id, 
                                        name=str(pos.get('name', 'Inconnu'))[:255], 
                                        asset_type=str(pos.get('asset_type', ''))[:255], 
                                        quantity=safe_float(pos.get('quantity')), 
                                        unit_price=safe_float(pos.get('unit_price')), 
                                        total_value=safe_float(pos.get('total_value'))
                                    )
                                    db.add(new_pos)
                                
                                profile.token_used_weekly += res.get("tokens", 0)
                                profile.token_used_daily += res.get("tokens", 0)
                                profile.token_used_global += res.get("tokens", 0)
                                
                                store_dir = f"/app/storage/{user['username']}/{acc_id}"
                                os.makedirs(store_dir, exist_ok=True)
                                t_path = st.session_state.get(f"path_{file_key}")
                                if t_path and os.path.exists(t_path): 
                                    shutil.move(t_path, f"{store_dir}/{e_date}.pdf")
                                
                                db.commit()
                                if profile.notify_discord: send_discord_msg(profile.discord_webhook, "🌌 Import Aura", f"Nouveau relevé importé : {e_bank}")
                                
                                st.session_state[f"done_{file_key}"] = True
                                del st.session_state[file_key]
                                db.close()
                                st.rerun()
                                
                            except Exception as err:
                                db.rollback()
                                st.error(f"❌ Erreur lors de l'enregistrement en base de données : {err}")
                
                elif f"done_{file_key}" in st.session_state:
                    st.success("✅ Document importé et sauvegardé avec succès ! Fermez le fichier (croix rouge) pour en ajouter un autre.")

        # ONGLET SAISIE MANUELLE
        with tab_manual:
            st.info("Recommandé pour les comptes statiques : Livret A, LDDS, LEP, Comptes Courants.")
            with st.form("manual_form", border=True):
                cm1, cm2 = st.columns(2)
                m_bank = cm1.text_input("Nom de la Banque (ex: Caisse d'Epargne, BoursoBank)")
                m_type = cm2.selectbox("Type de Compte", ["Livret A", "LDDS", "LEP", "Compte Courant", "PEL", "Autre"])
                
                cm3, cm4 = st.columns(2)
                m_val = cm3.number_input("Solde Actuel (€)", step=100.0, min_value=0.0)
                m_date = cm4.date_input("Date du solde", value=datetime.now())
                
                if st.form_submit_button("💾 Ajouter / Mettre à jour ce compte", type="primary"):
                    if m_bank:
                        exist_m = db.query(Account).filter_by(user_id=user["username"], bank_name=m_bank, account_type=m_type, is_manual=True).first()
                        if not exist_m:
                            exist_m = Account(user_id=user["username"], bank_name=m_bank, account_type=m_type, currency="EUR", total_invested=m_val, is_manual=True)
                            db.add(exist_m); db.commit(); db.refresh(exist_m)
                        else:
                            exist_m.total_invested = m_val 
                        
                        db.add(Record(account_id=exist_m.id, date_releve=m_date, total_value=m_val, total_invested=m_val, fonds_euro_value=m_val))
                        db.commit()
                        
                        st.toast(f"✅ {m_type} de {m_bank} mis à jour avec succès !", icon="💾")
                        st.success(f"Le compte {m_type} de {m_bank} a bien été enregistré avec un solde de {m_val:,.2f} €.")
                    else:
                        st.error("Veuillez renseigner le nom de la banque.")

        # ONGLET GESTION
        with tab_manage:
            accounts = db.query(Account).filter_by(user_id=user["username"]).all()
            if not accounts: st.write("Vous n'avez aucun compte d'enregistré pour le moment.")
            
            for acc in accounts:
                icon = "✍️" if acc.is_manual else "📂"
                with st.expander(f"{icon} {acc.bank_name} - {acc.account_type} {f'(N°{acc.contract_number})' if acc.contract_number else ''}"):
                    c_info, c_del = st.columns([0.8, 0.2])
                    c_info.write(f"Capital Actuel : **{acc.total_invested:,.2f} {acc.currency}**")
                    
                    if c_del.button("🗑️ Supprimer ce compte", key=f"del_acc_{acc.id}"): 
                        db.delete(acc); db.commit()
                        db.close()
                        st.rerun()
                    
                    if acc.records: 
                        render_account_history(acc.records)

    # --- PAGE : EXPORT ---
    elif menu == "📑 Export":
        st.header("📑 Exportation complète de vos données")
        accs = db.query(Account).filter_by(user_id=user["username"]).all()
        if accs:
            st.info("Cet export génère un fichier CSV contenant l'historique complet de tous vos comptes, avec les primes, fonds en euros et unités de compte.")
            if st.button("Générer l'export CSV exhaustif", type="primary"):
                data = []
                for a in accs:
                    for r in a.records:
                        data.append({
                            "Banque": a.bank_name,
                            "Type de Compte": a.account_type,
                            "Contrat/ID": a.contract_number,
                            "Devise": a.currency,
                            "Saisie Manuelle": "Oui" if a.is_manual else "Non",
                            "Date Relevé": r.date_releve,
                            "Valeur Totale": r.total_value,
                            "Capital Versé": r.total_invested,
                            "Valeur Fonds Euros": r.fonds_euro_value,
                            "Valeur Unités Compte": r.uc_value,
                            "Primes / Dividendes / Intéressement": r.dividends
                        })
                st.download_button("📥 Télécharger le fichier CSV", pd.DataFrame(data).to_csv(index=False), "export_patrimoine_complet.csv")
        else:
            st.warning("Aucune donnée à exporter. Commencez par ajouter des comptes.")

    # --- PAGE : PARAMÈTRES ---
    elif menu == "⚙️ Paramètres":
        st.header("⚙️ Configuration du compte")
        
        with st.container(border=True):
            st.subheader("💱 Devises affichées")
            curr = profile.active_currencies.split(",") if profile.active_currencies else ["EUR"]
            sel_c = st.multiselect("Sélectionnez les devises que vous utilisez", ["EUR", "CHF", "USD", "GBP", "CAD"], default=curr)
            st.caption("La devise principale reste l'Euro. Les autres devises s'afficheront en petit sous vos compteurs globaux dans le Dashboard.")
            
            st.divider()
            st.subheader("🔔 Notifications")
            profile.notify_discord = st.toggle("Activer les notifications Discord", profile.notify_discord)
            profile.discord_webhook = st.text_input("URL du Webhook Discord", profile.discord_webhook, type="password")
            
            if st.button("💾 Enregistrer les préférences", type="primary"): 
                profile.active_currencies = ",".join(sel_c)
                db.commit()
                st.success("Paramètres enregistrés avec succès !")

        st.divider()
        
        # DOUBLE VALIDATION POUR LE WIPE
        with st.expander("🚨 Zone de danger - Réinitialisation Totale"):
            st.warning("ATTENTION : Cette action effacera absolument toutes vos données (Comptes, Historique, PDF). Cette action est irréversible.")
            confirm_wipe = st.checkbox("Je confirme vouloir supprimer définitivement toutes mes données.")
            
            if confirm_wipe:
                if st.button("🗑️ Effacer toutes mes données", type="primary"):
                    for a in db.query(Account).filter_by(user_id=user["username"]).all(): 
                        db.delete(a)
                    
                    u_path = f"/app/storage/{user['username']}"
                    if os.path.exists(u_path): 
                        shutil.rmtree(u_path)
                    
                    db.commit()
                    db.close()
                    st.rerun()

    # --- PAGE : ADMIN ---
    elif menu == "🛡️ Admin":
        st.header("🛡️ Administration Système")
        
        tot_jour = db.query(func.sum(UserProfile.token_used_daily)).scalar() or 0
        st.subheader("🌐 Consommation Globale API Gemini (Aujourd'hui)")
        col_api, col_users = st.columns([0.7, 0.3])
        col_api.progress(min(tot_jour / 100000, 1.0), text=f"{tot_jour:,} tokens utilisés sur 100,000 (Limite Quotidienne API)")
        col_users.metric("Nombre d'Utilisateurs", db.query(UserProfile).count())

        st.divider()
        st.subheader("👥 Gestion des Quotas par Utilisateur")
        
        for p in db.query(UserProfile).all():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([0.2, 0.3, 0.3, 0.2])
                c1.write(f"👤 **{p.username}**")
                c2.write(f"📅 Conso Jour : {p.token_used_daily:,}")
                c3.write(f"🗓️ Conso Hebdo : {p.token_used_weekly:,} / {p.token_limit_weekly:,}")
                
                nl = c4.number_input("Modifier le Quota Hebdo", value=p.token_limit_weekly, key=f"limit_{p.id}", step=10000)
                if nl != p.token_limit_weekly: 
                    p.token_limit_weekly = nl
                    db.commit()
                    db.close()
                    st.rerun()

# --- BLOC DE SÉCURITÉ FINAL (ANTI-FUITE DE CONNEXIONS) ---
finally:
    db.close()
