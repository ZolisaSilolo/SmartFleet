/**
 * South African Locale Formatting Helpers (en-ZA)
 * Currency: ZAR (R)
 * Metrics: km, Litres (L), L/100km, R/km
 */

export function formatZAR(amount: number | null | undefined): string {
  if (amount === null || amount === undefined || isNaN(amount)) {
    return 'R 0.00';
  }
  return new Intl.NumberFormat('en-ZA', {
    style: 'currency',
    currency: 'ZAR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount).replace('ZAR', 'R');
}

export function formatKm(km: number | null | undefined): string {
  if (km === null || km === undefined || isNaN(km)) {
    return '0 km';
  }
  return `${new Intl.NumberFormat('en-ZA', { maximumFractionDigits: 1 }).format(km)} km`;
}

export function formatLPer100Km(val: number | null | undefined): string {
  if (val === null || val === undefined || isNaN(val)) {
    return '0.0 L/100km';
  }
  return `${val.toFixed(1)} L/100km`;
}

export function formatRandPerKm(val: number | null | undefined): string {
  if (val === null || val === undefined || isNaN(val)) {
    return 'R 0.00 / km';
  }
  return `R ${val.toFixed(2)} / km`;
}

export function formatDateSA(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return new Intl.DateTimeFormat('en-ZA', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }).format(d);
  } catch {
    return dateStr;
  }
}

export function formatDateTimeSA(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return new Intl.DateTimeFormat('en-ZA', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(d);
  } catch {
    return dateStr;
  }
}
