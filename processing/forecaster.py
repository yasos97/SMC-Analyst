import pandas as pd
import numpy as np
from statsmodels.tsa.holtwinters import ExponentialSmoothing

def generate_forecast(values: list[float], periods: int = 3) -> list[float]:
    """
    Génère une prévision sur X périodes futures pour une série temporelle donnée.
    Utilise Holt-Winters Exponential Smoothing avec fallback mathématique.
    """
    if not values or len(values) < 3:
        # Pas assez de données pour prévoir, on garde un fallback flat
        last_val = values[-1] if values else 0
        return [last_val] * periods
        
    s = pd.Series(values)
    
    try:
        # Si on a au moins 2 ans (24 mois), on peut utiliser la saisonnalité
        # Si < 24 mois, on utilise juste la tendance (trend)
        seasonal = 'add' if len(s) >= 24 else None
        seasonal_periods = 12 if len(s) >= 24 else None
        
        # S'il y a des zéros, on doit ajouter une constante minuscule si 'mul' est utilisé, 
        # mais on utilise 'add' donc ça ira.
        model = ExponentialSmoothing(
            s, 
            trend='add', 
            seasonal=seasonal, 
            seasonal_periods=seasonal_periods,
            initialization_method="estimated"
        ).fit()
        
        forecast = model.forecast(periods)
        
        # Empêcher des prévisions négatives pour le CA / Volumes
        forecast = [max(0, val) for val in forecast.tolist()]
        return forecast
        
    except Exception as e:
        print(f"[SalamaIQ Forecaster] Erreur Holt-Winters: {e}")
        # Fallback ultra robuste mathématique simple (Moyenne Mobile Pondérée sur les 3 derniers)
        return _simple_moving_average_forecast(values, periods)

def _simple_moving_average_forecast(values: list[float], periods: int) -> list[float]:
    """
    Prévision naïve (Moyenne mobile) si l'IA algorithmique échoue.
    """
    recent = values[-3:]
    forecast = []
    for _ in range(periods):
        next_val = sum(recent) / len(recent)
        forecast.append(next_val)
        recent.append(next_val)
        recent = recent[1:]
    return forecast
