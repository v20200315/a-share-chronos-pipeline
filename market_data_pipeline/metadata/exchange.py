def infer_exchange(code: str) -> str:
    """Infer A-share exchange from 6-digit code prefix."""

    normalized = str(code).zfill(6)

    if normalized.startswith(('60', '68')):
        return 'SH'
    if normalized.startswith(('00', '30')):
        return 'SZ'
    if normalized.startswith(('43', '83', '87', '88', '92', '4', '8')):
        return 'BJ'

    return 'UNKNOWN'
