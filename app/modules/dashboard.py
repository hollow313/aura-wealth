import streamlit as st
import pandas as pd
from database import Account, Record
from utils import convert_to_eur, get_multi_currency_caption
from modules.charts import render_patrimoine_chart, render_allocation_chart, render_treemap_allocation

def render_dashboard(user, profile, db):
    st.header("📈 Dashboard Patrimonial")
    accounts = db.query(Account).filter_by(user_id=user["username"]).all()
    
    if not accounts:
        st.info("👋 Bienvenue ! Ajoutez vos premiers investissements dans l'onglet **💳 Patrimoine & PDF**.")
        return

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
                all_positions.append({"Compte": a.bank_name, "Actif": pos.name, "Valeur": f"{pos.total_value:,.2f} {a.currency}"})

    k1, k2, k3, k4 = st.columns(4)
    
    k1.metric("Capital Versé Global", f"{total_inv_eur:,.0f} €")
    if sub_inv := get_multi_currency_caption(total_inv_eur, profile.active_currencies): k1.caption(sub_inv)
        
    k2.metric("Valeur Marché Globale", f"{total_val_eur:,.2f} €")
    if sub_val := get_multi_currency_caption(total_val_eur, profile.active_currencies): k2.caption(sub_val)
        
    gain_tot = total_val_eur - total_inv_eur
    k3.metric("Plus-Value Nette", f"{gain_tot:+.2f} €", f"{(gain_tot/total_inv_eur*100):+.2f}%" if total_inv_eur > 0 else "0%")
    if sub_gain := get_multi_currency_caption(gain_tot, profile.active_currencies): k3.caption(sub_gain)
        
    k4.metric("Primes / Intéressement", f"{total_div_eur:,.2f} €")
    if sub_div := get_multi_currency_caption(total_div_eur, profile.active_currencies): k4.caption(sub_div)

    st.divider()
    
    # NOUVELLE VUE : Camembert + Treemap + Allocation
    c_l, c_m, c_r = st.columns(3)
    with c_l: 
        st.subheader("Répartition par Compte")
        render_patrimoine_chart(accounts)
    with c_m: 
        st.subheader("Carte des Actifs (Treemap)")
        render_treemap_allocation(accounts)
    with c_r: 
        st.subheader("Sécurité vs Risque")
        render_allocation_chart(total_euro_eur, total_uc_eur)
    
    st.divider()
    
    st.subheader("📋 Résumé des Portefeuilles")
    st.dataframe(pd.DataFrame(perf_summary), hide_index=True, use_container_width=True)
    if all_positions:
        st.subheader("🔍 Détail des Actifs")
        st.dataframe(pd.DataFrame(all_positions), hide_index=True, use_container_width=True)
