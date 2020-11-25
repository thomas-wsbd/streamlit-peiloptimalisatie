import numpy as np


def get_debiet_marksluis(
    verval, hoogtes_schuiven=[0.7, 0.7, 0.7, 0.7, 0.8, 0.8, 0.8, 0.8], c_wrijving=0.63
):
    # Initialiseer het debiet op 0
    Q = 0

    # Voor elke opening voegen we debiet toe
    for schuifhoogte in hoogtes_schuiven:
        Q += 1.3 * schuifhoogte * 0.6 * c_wrijving * np.sqrt(2 * 9.81 * verval)

    return Q


def get_debiet_inlaatduiker(verval, m_constant=1, schuifhoogte=1.78, breedte_duiker=1.75):
    """
    Deze functie berekent het debiet voor een inlaatduiker onder vrij verval.

    Parameters
    ----------
    verval: float
        verschil tussen H_bov en H_ben in meters
    m_constant: float
        de M-constante voor de duiker
    schuifhoogte: float
        hoogte van de schuif/duiker in meters
    breedte_duiker: float
        breedte van de schuif/duiker in meters

    Returns
    -------
    debiet: float
        debiet in m3/s
    """
    return m_constant * schuifhoogte * breedte_duiker * np.sqrt(2 * 9.81 * verval)


def get_hben_voor_debiet(debiet, h_bov, m_constant=1, schuifhoogte=1.78, breedte_duiker=1.75):
    """
    Deze functie berekent H_ben voor een inlaatduiker onder vrij verval, gegeven het debiet en
    de H_bov. Dit is dus de functie in get_debiet_inlaatduiker omgeschreven naar H_ben.

    Parameters
    ----------
    debiet: float
        debiet in m3/s
    h_bov: float
        de waterstand aan de instroomkant van de duiker in meters
    m_constant: float
        de M-constante voor de duiker
    schuifhoogte: float
        hoogte van de schuif/duiker in meters
    breedte_duiker: float
        breedte van de schuif/duiker in meters

    Returns
    -------
    H_ben: float
        benedenstroomse waterstand in meters
    """
    return h_bov - np.square(Q / (m_constant * schuifhoogte * breedte_duiker)) / (2 * 9.81)


def get_watervraag(
    doorspoelprotocol=True,
    droog_jaar=True,
    aanvoer_gemiddeld_jaar=0.1,
    aanvoer_droog_jaar=0.3,
    afvoer_doorspoel=4.8,
    areaal=28100,
):
    return (
        0.001
        * areaal
        * (droog_jaar * aanvoer_droog_jaar + (not droog_jaar) * aanvoer_gemiddeld_jaar)
        + doorspoelprotocol * afvoer_doorspoel
    )
