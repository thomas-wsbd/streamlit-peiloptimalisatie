import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sklearn.linear_model import LinearRegression

from assets.locations_wsss import LOCATIES_WSSS
from vzm.utilities import *

COL_VZM = "VZM_WT"

@st.cache(allow_output_mutation=True)
def load_abt():
    # Load the data
    abt = pd.read_feather("data\\abt_feat.feather")

    # Fix the timezone issues in streamlit
    abt["datetime"] = abt["datetime"].dt.tz_localize("UTC")

    # Set the correct index
    abt = abt.set_index("datetime")

    return abt

@st.cache
def get_train_cols_wsbd(abt, col_wth_beneden):
    return abt[[col_wth_beneden, "maand_dag", "BAW_afvoer"]]


@st.cache
def train_model_wsbd(abt, z=1.96):
    X = get_train_cols_wsbd(abt, "4510_WTH_BEN")
    y = abt[COL_VZM]

    lr = LinearRegression().fit(X, y)

    y_hat = lr.predict(get_train_cols_wsbd(abt, "4510_WTH_BEN"))

    # estimate stdev of yhat
    sum_errs = np.sum((y - y_hat) ** 2)
    stdev = np.sqrt(1 / (len(y) - 2) * sum_errs)
    interval = z * stdev

    return lr, interval


@st.cache
def get_train_cols_wsss(abt, col_wth_boven):
    return abt[
        [col_wth_boven, "maand_dag"]
        + [col for col in abt.columns if "_FHX" in col or "_FHVEC" in col]
    ]


@st.cache
def train_model_wsss(abt, col_wth_boven, z=1.96):
    X = get_train_cols_wsss(abt, col_wth_boven)
    y = abt[COL_VZM]
    lr = LinearRegression().fit(X, y)

    y_hat = lr.predict(get_train_cols_wsss(abt, col_wth_boven))

    # estimate stdev of yhat
    sum_errs = np.sum((y - y_hat) ** 2)
    stdev = np.sqrt(1 / (len(y) - 2) * sum_errs)
    interval = z * stdev

    return lr, interval


@st.cache(allow_output_mutation=True)
def get_series_wsbd(
    abt,
    droge_jaren=[],
    use_marksluis=False,
    areaal=28100,
    aanvoer_gemiddeld_jaar=0.1,
    aanvoer_droog_jaar=0.3,
):
    # Maak kopie van de data
    data = abt.copy()

    # Historisch
    data["Q_WSBD_totaal_historisch"] = data["Totale_afvoer"]

    # Theoretisch, Marksluis moet hier nog bij
    data["Q_WSBD_totaal_theoretisch"] = data["BAW_afvoer"] + get_debiet_inlaatduiker(
        data["4510_WTH_BOV"] - data["4510_WTH_BEN"]
    )

    # Benodigd
    data["Q_WSBD_totaal_nodig"] = get_watervraag(
        doorspoelprotocol=(data["verblijftijd_VDE_mean_7days"] >= 12),
        droog_jaar=False,
        aanvoer_gemiddeld_jaar=aanvoer_gemiddeld_jaar,
        aanvoer_droog_jaar=aanvoer_droog_jaar,
        areaal=areaal,
    )

    # Droogte
    for jaar in droge_jaren:
        data.loc[
            (data.index >= str(jaar) + "-05-01") & (data.index <= str(jaar) + "-10-01"),
            "Q_WSBD_totaal_nodig",
        ] = get_watervraag(
            doorspoelprotocol=(data["verblijftijd_VDE_mean_7days"] >= 12),
            droog_jaar=True,
            aanvoer_gemiddeld_jaar=aanvoer_gemiddeld_jaar,
            aanvoer_droog_jaar=aanvoer_droog_jaar,
            areaal=areaal,
        )

    # Benodigd debiet en waterstand, Marksluis moet hier nog bij
    data["Q_WSBD_4510_nodig"] = data["Q_WSBD_totaal_nodig"] - data["BAW_afvoer"]

    if use_marksluis:
        data["Q_WSBD_4510_nodig"] = data["Q_WSBD_4510_nodig"] - get_debiet_marksluis(
            data["4510_WTH_BOV"] - data["4510_WTH_BEN"]
        )

    data["Q_WSBD_4510_nodig"] = data["Q_WSBD_4510_nodig"].clip(lower=0)

    data["4510_WTH_BEN_nodig"] = get_hben_voor_debiet_inlaatduiker(
        debiet=data["Q_WSBD_4510_nodig"],
        h_bov=data["4510_WTH_BOV"],
        m_constant=0.87,
        schuifhoogte=1.78,
        breedte_duiker=1.75,
    )

    # Voorspel peil op VZM
    model, conf_int = train_model_wsbd(abt)
    data["WSBD_VZM_WT_gewenst"] = model.predict(
        get_train_cols_wsbd(data, "4510_WTH_BEN_nodig").fillna(0)
    )

    # Confidence intervals
    data["WSBD_VZM_WT_gewenst_conf_upper"] = data["WSBD_VZM_WT_gewenst"] + conf_int
    data["WSBD_VZM_WT_gewenst_conf_lower"] = data["WSBD_VZM_WT_gewenst"] - conf_int

    return data[
        ["WSBD_VZM_WT_gewenst", "WSBD_VZM_WT_gewenst_conf_upper", "WSBD_VZM_WT_gewenst_conf_lower"]
    ]


@st.cache(allow_output_mutation=True)
def get_series_wsss(
    abt, droge_jaren=[], arealen={}, aanvoer_gemiddeld_jaar=0.1, aanvoer_droog_jaar=0.3
):
    # Maak kopie van de data
    data = abt.copy()

    # Lijst voor opslaan welke kolommen we willen returnen
    l_return = []

    for locatie in LOCATIES_WSSS:
        # Historisch
        data[f"Q_WSSS_{locatie['name_short']}_historisch"] = abt[locatie["inlaat_q"]]

        # Theoretisch
        if locatie["type"] == "inlaatduiker":
            data[f"Q_WSSS_{locatie['name_short']}_theoretisch"] = get_debiet_inlaatduiker(
                verval=data[locatie["inlaat_wt_bov"]] - data[locatie["inlaat_wt_ben"]],
                m_constant=locatie["m_constant"],
                schuifhoogte=locatie["schuifhoogte"],
                breedte_duiker=locatie["breedte_duiker"],
            )
        if locatie["type"] == "stuw":
            data[f"Q_WSSS_{locatie['name_short']}_theoretisch"] = get_debiet_stuw(
                verval=data[locatie["inlaat_wt_bov"]] - data[locatie["inlaat_wt_ben"]],
                c_constant=locatie["c_constant"],
                m_constant=locatie["m_constant"],
                breedte_stuw=locatie["breedte_stuw"],
            )

        # Nodig
        data[f"Q_WSSS_{locatie['name_short']}_totaal_nodig"] = get_watervraag(
            doorspoelprotocol=False,
            droog_jaar=False,
            areaal=arealen["wsss_" + locatie["name_short"]],
        )

        # Droogte
        for jaar in droge_jaren:
            data.loc[
                (data.index >= str(jaar) + "-05-01") & (data.index <= str(jaar) + "-10-01"),
                f"Q_WSSS_{locatie['name_short']}_totaal_nodig",
            ] = get_watervraag(
                doorspoelprotocol=False,
                droog_jaar=True,
                areaal=arealen["wsss_" + locatie["name_short"]],
            )

        # Benodigd debiet en waterstand, Marksluis moet hier nog bij
        data[f"Q_WSSS_{locatie['name_short']}_nodig"] = data[
            f"Q_WSSS_{locatie['name_short']}_totaal_nodig"
        ].clip(0)

        if locatie["type"] == "inlaatduiker":
            data[f"{locatie['name_short']}_WTH_BOV_nodig"] = get_hbov_voor_debiet_inlaatduiker(
                debiet=data[f"Q_WSSS_{locatie['name_short']}_nodig"],
                h_ben=data[locatie["inlaat_wt_ben"]],
                m_constant=locatie["m_constant"],
                schuifhoogte=locatie["schuifhoogte"],
                breedte_duiker=locatie["breedte_duiker"],
            )
        if locatie["type"] == "stuw":
            data[f"{locatie['name_short']}_WTH_BOV_nodig"] = get_hbov_voor_debiet_stuw(
                debiet=data[f"Q_WSSS_{locatie['name_short']}_nodig"],
                h_ben=data[locatie["inlaat_wt_ben"]],
                c_constant=locatie["c_constant"],
                m_constant=locatie["m_constant"],
                breedte_stuw=locatie["breedte_stuw"],
            )

        model, _ = train_model_wsss(abt, locatie["inlaat_wt_bov"])

        data[f"WSSS_{locatie['name_short']}_VZM_WT_gewenst"] = model.predict(
            get_train_cols_wsss(data, f"{locatie['name_short']}_WTH_BOV_nodig").fillna(0)
        )

        l_return.append(f"WSSS_{locatie['name_short']}_VZM_WT_gewenst")

    return data[l_return]


### SIDEBAR ###
st.sidebar.header("Opties")

st.sidebar.subheader("Droogte")
droge_jaren = st.sidebar.multiselect("Droge jaren", list(range(2016, 2020)), [2018])

## AREALEN
ags = {}
st.sidebar.subheader("Areaalgroottes")
ags["wsbd"] = st.sidebar.number_input("WS Brabantse Delta", value=28100, step=100)
ags["wsss_vanhaaften"] = st.sidebar.number_input(
    "WS Scheldestromen: Van Haaften", value=6530, step=100
)
ags["wsss_campweg"] = st.sidebar.number_input("WS Scheldestromen: Campweg", value=1930, step=100)
ags["wsss_driegrotepolders"] = st.sidebar.number_input(
    "WS Scheldestromen: Drie Grote Polders", value=2915, step=100
)

## WATER BENODIGD
wv = {"wsbd": {}, "wsss": {}}
st.sidebar.subheader("Watervolumes nodig (l/s/ha)")
wv["wsbd"]["normaal"] = st.sidebar.number_input("WS Brabantse Delta: normaal", value=0.1, step=0.1)
wv["wsbd"]["droog"] = st.sidebar.number_input("WS Brabantse Delta: droog", value=0.3, step=0.1)
wv["wsss"]["normaal"] = st.sidebar.number_input("WS Scheldestromen: normaal", value=0.1, step=0.1)
wv["wsss"]["droog"] = st.sidebar.number_input("WS Scheldestromen: droog", value=0.3, step=0.1)

## OVERIGE OPTIES
st.sidebar.subheader("Overige opties")
use_marksluis = st.sidebar.checkbox("Aanvoer via Marksluis")

### MAIN ###
st.title("Peiloptimalisatie VZM")

st.header("Opties voor de visualisatie")

smooth_wts = st.checkbox("Smooth de waterstanden naar daggemiddelden", True)
clip_wts = st.checkbox("Begrens de gewenste waterstanden op de peiltrap", False)
summarize_wsss = st.checkbox("Vat de peilen van WSSS samen in een maximum-peil", False)
conf_int_wsbd = st.checkbox("Plot het 95% confidence interval voor WSBD", False)

st.header("Resultaten van analyse")

# Laad de ABT
abt = load_abt()

# WSBD
df_wsbd = get_series_wsbd(
    abt,
    droge_jaren=droge_jaren,
    use_marksluis=use_marksluis,
    areaal=ags["wsbd"],
    aanvoer_droog_jaar=wv["wsbd"]["droog"],
    aanvoer_gemiddeld_jaar=wv["wsbd"]["normaal"],
)

# WSSS
df_wsss = get_series_wsss(
    abt,
    droge_jaren=droge_jaren,
    arealen=ags,
    aanvoer_droog_jaar=wv["wsss"]["droog"],
    aanvoer_gemiddeld_jaar=wv["wsss"]["normaal"],
)

### VISUAL ###

vzm_peil = abt[COL_VZM].copy()

if smooth_wts:
    vzm_peil = vzm_peil.resample("D").mean()
    df_wsbd = df_wsbd.resample("D").mean()
    df_wsss = df_wsss.resample("D").mean()

if clip_wts:
    df_wsbd = df_wsbd.clip(abt["ptonder"], abt["ptboven"])
    df_wsss = df_wsss.clip(abt["ptonder"], abt["ptboven"])

fig = go.Figure()

# VZM-peil
fig.add_trace(
    go.Scatter(
        x=vzm_peil.index,
        y=vzm_peil,
        mode="lines",
        name=COL_VZM,
        line=dict(color="rgb(251,106,74)"),
    )
)

# WSBD
fig.add_trace(
    go.Scatter(
        x=df_wsbd.index,
        y=df_wsbd["WSBD_VZM_WT_gewenst"],
        mode="lines",
        name="WSBD_VZM_WT_gewenst",
        line=dict(color="rgb(66,146,198)"),
    )
)

if conf_int_wsbd:
    fig.add_trace(
        go.Scatter(
            x=df_wsbd.index,
            y=df_wsbd["WSBD_VZM_WT_gewenst_conf_upper"],
            mode="lines",
            name="WSBD_VZM_WT_gewenst_upper",
            line=dict(color="rgb(158,202,225)"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df_wsbd.index,
            y=df_wsbd["WSBD_VZM_WT_gewenst_conf_lower"],
            mode="lines",
            name="WSBD_VZM_WT_gewenst_lower",
            line=dict(color="rgb(158,202,225)"),
        )
    )

# WSSS
if summarize_wsss:
    # color_list = ["rgb(224,224,223)", "rgb(197,197,195)", "rgb(171,171,170)"]
    color_list = ["rgb(224,224,223)"] * len(df_wsss.columns)
else:
    color_list = ["rgb(116,196,118)", "rgb(65,171,93)", "rgb(35,139,69)"]

# Plot the rest of WSSS
i = 0
for inlaat in df_wsss.columns:
    fig.add_trace(
        go.Scatter(
            x=df_wsss.index,
            y=df_wsss[inlaat],
            mode="lines",
            name=inlaat,
            line=dict(color=color_list[i]),
        )
    )
    i += 1

if summarize_wsss:
    df_wsss_max = df_wsss.max(axis=1)

    fig.add_trace(
        go.Scatter(
            x=df_wsss_max.index,
            y=df_wsss_max,
            mode="lines",
            name="WSSS_max_VZM_WT_gewenst",
            line=dict(color="rgb(35,139,69)"),
        )
    )


# Peilbesluit
fig.add_shape(
    dict(
        type="line",
        x0=abt.index.min(),
        y0=0.15,
        x1=abt.index.max(),
        y1=0.15,
        line=dict(dash="dot", color="#999"),
    )
)

fig.add_shape(
    dict(
        type="line",
        x0=abt.index.min(),
        y0=-0.1,
        x1=abt.index.max(),
        y1=-0.1,
        line=dict(dash="dot", color="#999"),
    )
)

# Peiltrap
fig.add_trace(
    go.Scatter(
        x=abt.index,
        y=abt["ptboven"],
        name="Bovenkant peiltrap",
        line={"dash": "dash", "color": "grey"},
    )
)

fig.add_trace(
    go.Scatter(
        x=abt.index,
        y=abt["ptonder"],
        name="Onderkant peiltrap",
        line={"dash": "dash", "color": "grey"},
    )
)

fig.update_layout(height=800)

st.plotly_chart(fig, use_container_width=True)

st.header("Uitleg, aannames")
st.write(
    f"""
- Voor het gewogen VZM-peil gebruiken we kolom `{COL_VZM}`
- Voor Campweg wordt nu het gewogen VZM-peil als bovenstrooms peil genomen. Daardoor negeren we het effect van de aanjager en mogelijk verschil tussen het gewogen VZM-peil en het peil bij de stuw zelf.
"""
)
