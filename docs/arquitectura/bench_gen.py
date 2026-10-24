"""Genera docs/img/bench_comparacion.png con las cifras de reportes/paso13_banco.md (500 solicitudes sintéticas)."""
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
D = [('A · Este sistema', 95664, '66,1 % óptimo'), ('B · Jev', 159419, '50,7 % óptimo'), ('C · LLM', None, None),
     ('Siempre el más barato', 205423, '49,9 % óptimo'), ('Aleatorio', 386392, '27,2 % óptimo')]
fig, ax = plt.subplots(figsize=(9.5, 4.0), dpi=150)
ys = list(range(len(D)))[::-1]
cols = ['#00508f', '#8a5200', '#8a5200', '#b9b6ad', '#b9b6ad']
for y, (n, v, e), c in zip(ys, D, cols):
    if v is None:
        ax.text(2000, y, 'no medido (falta la clave de API)', va='center', fontsize=9, color='#555', style='italic'); continue
    ax.barh(y, v, color=c, height=0.6)
    ax.text(v + 4000, y, f'${v:,.0f}'.replace(',', '.') + f'  ·  {e}', va='center', fontsize=9, color='#222')
ax.set_yticks(ys, [d[0] for d in D], fontsize=10)
ax.set_xlim(0, 520000)
ax.set_xlabel('Arrepentimiento medio por servicio (COP, verdad oculta; menor es mejor)')
ax.set_title('Comparación de motores · 500 solicitudes sintéticas', fontsize=11, loc='left', fontweight='bold')
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v/1000:,.0f} mil'.replace(',', '.')))
for s in ('top', 'right'): ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig('../img/bench_comparacion.png'); print('ok')
