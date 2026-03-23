from datetime import date

def meses_entre(inicio: date, fin: date):
    """
    Genera una lista de objetos date (primer día del mes)
    desde 'inicio' hasta 'fin', ambos inclusive.
    """
    meses = []
    y, m = inicio.year, inicio.month

    while (y < fin.year) or (y == fin.year and m <= fin.month):
        meses.append(date(y, m, 1))
        m += 1
        if m > 12:
            m = 1
            y += 1

    return meses
