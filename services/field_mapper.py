# -*- coding: utf-8 -*-
"""Normalize indicator field names to stable API keys using uploaded XLSX Chinese headers."""
import pandas as pd
from typing import Dict, Any

# Mapping from Chinese headers to API keys
CN_TO_API = {
    '市場別': 'market',
    '股票代號': 'ticker',
    '股票簡稱': 'name',
    '產業名稱': 'industry',
    '最新股價': 'close',
    '最新日期': 'date',
    'MA_數值': 'ma_value',
    'MA_分析': 'ma_signal',
    'KD_數值': 'kd_value',
    'KD_分析': 'kd_signal',
    'MACD_數值': 'macd_value',
    'MACD_分析': 'macd_signal',
    'RSI_數值': 'rsi_value',
    'RSI_分析': 'rsi_signal',
    'PSY_數值': 'psy_value',
    'PSY_分析': 'psy_signal',
    'BIAS_數值': 'bias_value',
    'BIAS_分析': 'bias_signal',
    'W%R_數值': 'wr_value',
    'W%R_分析': 'wr_signal',
    'BANDS_數值': 'bb_value',
    'BANDS_分析': 'bb_signal',
    'OBV_數值': 'obv_value',
    'OBV_分析': 'obv_signal',
    'ROE_數值': 'roe_value',
    'ROE_分析': 'roe_signal',
    '負債比率_數值': 'de_ratio_value',
    '負債比率_分析': 'de_ratio_signal',
    '利息保障倍數_數值': 'int_cov_value',
    '利息保障倍數_分析': 'int_cov_signal',
    '流動比率_數值': 'cr_value',
    '流動比率_分析': 'cr_signal',
}

def normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in row.items():
        key = CN_TO_API.get(k, k)
        out[key] = v
    # Ensure minimal fields exist
    out.setdefault('ticker', row.get('股票代號') or row.get('ticker'))
    out.setdefault('name', row.get('股票簡稱') or row.get('name'))
    out.setdefault('market', row.get('市場別') or row.get('market'))
    out.setdefault('industry', row.get('產業名稱') or row.get('industry'))
    out.setdefault('close', row.get('最新股價') or row.get('close'))
    out.setdefault('date', row.get('最新日期') or row.get('date'))
    return out
