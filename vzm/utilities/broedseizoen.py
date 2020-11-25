import pandas as pd


def add_broedseizoen(df, stuurgrenzen=False):
    # Voeg maand-dag toe
    # Dit gaat er vanuit dat de index een timestamp is
    df["maand_dag"] = df.index.strftime("%m%d")
    df["maand_dag"] = df["maand_dag"].astype(int)

    # Maak dataframe met peiltrappen
    if stuurgrenzen:
        df_pt = [
            [101, 229, 0.13, -0.05],
            [301, 314, 0.13, 0.07],
            [315, 414, 0.09, 0.03],
            [415, 514, 0.05, -0.01],
            [515, 614, 0.01, -0.05],
            [615, 714, -0.02, -0.08],
            [715, 1231, 0.13, -0.05],
        ]
    else:
        # Peilgrenzen
        df_pt = [
            [101, 229, 0.15, -0.10],
            [301, 314, 0.15, 0.05],
            [315, 414, 0.11, 0.01],
            [415, 514, 0.07, -0.03],
            [515, 614, 0.03, -0.07],
            [615, 714, 0.00, -0.10],
            [715, 1231, 0.15, -0.10],
        ]

    df_pt = pd.DataFrame(df_pt, columns=["start", "end", "boven", "onder"])

    df_pti = df_pt.set_index(["start", "end"])
    df_pti.index = pd.IntervalIndex.from_tuples(df_pti.index, closed="both")

    df["ptboven"] = df["maand_dag"].map(df_pti["boven"])
    df["ptonder"] = df["maand_dag"].map(df_pti["onder"])

    return df
