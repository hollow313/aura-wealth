import streamlit as st
import os, shutil
from datetime import datetime
from database import Account, Record, Position
from parser import check_quota_and_parse
from modules.charts import render_account_history
from modules.notifications import send_discord_msg
from utils import safe_float

def render_patrimoine(user, profile, db):
    st.header("💳 Gestion des Investissements (Patrimoine)")
    tab_import, tab_manual, tab_manage = st.tabs(["📥 Import PDF (IA)", "✍️ Saisie Manuelle", "📂 Gérer mes comptes"])
    
    # --- IMPORT IA ---
    with tab_import:
        st.info("Glissez votre relevé PDF (Assurance Vie, PEA, Amundi, Natixis...).")
        up_file = st.file_uploader("Fichier PDF", type="pdf", label_visibility="collapsed")
        
        if up_file:
            file_key = f"pdf_{up_file.file_id}"
            
            if file_key not in st.session_state and f"done_{file_key}" not in st.session_state:
                with st.status("🔮 L'IA lit votre document en profondeur...", expanded=True) as status:
                    t_path = f"/tmp/{up_file.file_id}.pdf"
                    with open(t_path, "wb") as f: f.write(up_file.getvalue())
                        
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
                    c1, c2, c3 = st.columns(3)
                    e_bank = c1.text_input("Banque", value=res.get("bank_name", ""))
                    e_date = c2.text_input("Date (YYYY-MM-DD)", value=res.get("date", ""))
                    e_curr = c3.selectbox("Devise", ["EUR", "CHF", "USD", "GBP", "CAD"], index=0)
                    
                    c4, c5, c6 = st.columns(3)
                    e_val = c4.number_input("Valeur Totale", value=safe_float(res.get("total_value")), step=10.0)
                    e_inv = c5.number_input("Capital Versé", value=safe_float(res.get("total_invested")), step=10.0)
                    e_div = c6.number_input("Primes/Intéressement", value=safe_float(res.get("dividends")), step=10.0)
                    
                    e_type = st.text_input("Type de compte", value=res.get("account_type", ""))
                    
                    with st.expander("Voir le détail brut des actifs"): st.json(res.get("positions", []))
                    
                    existing = db.query(Account).filter_by(user_id=user["username"]).all()
                    opts = {f"{a.bank_name} - {a.account_type} (N°{a.contract_number})": a.id for a in existing if not a.is_manual}
                    opts["➕ Créer un nouveau compte PDF"] = "NEW"
                    target = st.selectbox("Assigner ce relevé à :", options=opts.keys())
                    
                    if st.form_submit_button("💾 Sauvegarder", type="primary"):
                        try:
                            acc_id = opts[target]
                            try: p_date = datetime.strptime(e_date, "%Y-%m-%d").date()
                            except: p_date = datetime.now().date()

                            if acc_id == "NEW":
                                new_a = Account(user_id=user["username"], bank_name=e_bank, account_type=e_type, contract_number=res.get("contract_number"), currency=e_curr, total_invested=e_inv, is_manual=False)
                                db.add(new_a); db.commit(); db.refresh(new_a); acc_id = new_a.id
                            else:
                                db.get(Account, acc_id).total_invested = e_inv

                            new_r = Record(account_id=acc_id, date_releve=p_date, total_value=e_val, total_invested=e_inv, fonds_euro_value=safe_float(res.get("fonds_euro_value")), uc_value=safe_float(res.get("uc_value")), dividends=e_div)
                            db.add(new_r); db.commit(); db.refresh(new_r)
                            
                            for pos in res.get("positions", []):
                                db.add(Position(record_id=new_r.id, name=str(pos.get('name', ''))[:255], asset_type=str(pos.get('asset_type', ''))[:255], quantity=safe_float(pos.get('quantity')), unit_price=safe_float(pos.get('unit_price')), total_value=safe_float(pos.get('total_value'))))
                            
                            profile.token_used_weekly += res.get("tokens", 0)
                            profile.token_used_daily += res.get("tokens", 0)
                            profile.token_used_global += res.get("tokens", 0)
                            
                            store_dir = f"/app/storage/{user['username']}/{acc_id}"
                            os.makedirs(store_dir, exist_ok=True)
                            t_path = st.session_state.get(f"path_{file_key}")
                            if t_path and os.path.exists(t_path): shutil.move(t_path, f"{store_dir}/{e_date}.pdf")
                            
                            db.commit()
                            if profile.notify_discord: send_discord_msg(profile.discord_webhook, "🌌 Import", f"Nouveau relevé importé : {e_bank}")
                            
                            st.session_state[f"done_{file_key}"] = True
                            del st.session_state[file_key]
                            db.close(); st.rerun()
                        except Exception as err:
                            db.rollback(); st.error(f"❌ Erreur : {err}")
            
            elif f"done_{file_key}" in st.session_state:
                st.success("✅ Document sauvegardé avec succès ! Fermez le fichier pour en ajouter un autre.")

    # --- SAISIE MANUELLE ---
    with tab_manual:
        st.info("Recommandé pour les comptes statiques : Livret A, LDDS, LEP.")
        with st.form("manual_form", border=True):
            cm1, cm2 = st.columns(2)
            m_bank = cm1.text_input("Nom de la Banque (ex: Caisse d'Epargne)")
            m_type = cm2.selectbox("Type de Compte", ["Livret A", "LDDS", "LEP", "Compte Courant", "PEL", "Autre"])
            
            cm3, cm4 = st.columns(2)
            m_val = cm3.number_input("Solde Actuel (€)", step=100.0, min_value=0.0)
            m_date = cm4.date_input("Date du solde", value=datetime.now())
            
            if st.form_submit_button("💾 Ajouter / Mettre à jour", type="primary"):
                if m_bank:
                    exist_m = db.query(Account).filter_by(user_id=user["username"], bank_name=m_bank, account_type=m_type, is_manual=True).first()
                    if not exist_m:
                        exist_m = Account(user_id=user["username"], bank_name=m_bank, account_type=m_type, currency="EUR", total_invested=m_val, is_manual=True)
                        db.add(exist_m); db.commit(); db.refresh(exist_m)
                    else:
                        exist_m.total_invested = m_val 
                    
                    db.add(Record(account_id=exist_m.id, date_releve=m_date, total_value=m_val, total_invested=m_val, fonds_euro_value=m_val))
                    db.commit()
                    st.toast(f"✅ {m_type} mis à jour !", icon="💾")
                else:
                    st.error("Veuillez renseigner le nom de la banque.")

    # --- GESTION ---
    with tab_manage:
        accounts = db.query(Account).filter_by(user_id=user["username"]).all()
        for acc in accounts:
            icon = "✍️" if acc.is_manual else "📂"
            with st.expander(f"{icon} {acc.bank_name} - {acc.account_type}"):
                c_info, c_del = st.columns([0.8, 0.2])
                c_info.write(f"Capital Actuel : **{acc.total_invested:,.2f} {acc.currency}**")
                if c_del.button("🗑️ Supprimer", key=f"del_acc_{acc.id}"): 
                    db.delete(acc); db.commit(); db.close(); st.rerun()
                if acc.records: render_account_history(acc.records)
