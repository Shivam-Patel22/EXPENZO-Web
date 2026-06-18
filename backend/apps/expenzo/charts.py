import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64

def generate_savings_gauge_chart(percent):
    try:
        percent = max(0.0, min(100.0, float(percent)))
        remaining = 100.0 - percent

        # Don't show empty charts if remaining is 100 and percent is 0
        if percent == 0:
            sizes = [0.001, 99.999]
        else:
            sizes = [percent, remaining]

        fig, ax = plt.subplots(figsize=(1.2, 1.2), dpi=200)
        fig.patch.set_alpha(0.0)
        ax.patch.set_alpha(0.0)

        # Set Colors
        colors = ['#34d399', (1.0, 1.0, 1.0, 0.06)]

        # Donut plot
        ax.pie(
            sizes,
            colors=colors,
            startangle=90,
            counterclock=False,
            wedgeprops=dict(width=0.16, edgecolor='none')
        )

        ax.text(
            0, 0, f"{int(percent)}%",
            ha='center', va='center',
            fontsize=12, color='#f8fafc',
            weight='bold', fontfamily='sans-serif'
        )

        ax.axis('equal')
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0, transparent=True)
        plt.close(fig)
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception as e:
        print("Error generating gauge chart:", e)
        return ""

def generate_spending_pie_chart(categories, values):
    try:
        if not values or sum(values) == 0:
            return None

        fig, ax = plt.subplots(figsize=(2.0, 2.0), dpi=200)
        fig.patch.set_alpha(0.0)
        ax.patch.set_alpha(0.0)

        # Custom high contrast palette matching our categories color scheme
        colors = ["#818cf8", "#34d399", "#fb7185", "#fbbf24", "#a78bfa", "#22d3ee", "#f472b6", "#a7f3d0", "#c084fc", "#94a3b8"]
        colors = colors[:len(categories)]

        ax.pie(
            values,
            colors=colors,
            startangle=90,
            counterclock=False,
            wedgeprops=dict(width=0.25, edgecolor='none')
        )

        ax.axis('equal')
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0, transparent=True)
        plt.close(fig)
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception as e:
        print("Error generating pie chart:", e)
        return None

def generate_group_net_standing_chart(names, nets):
    try:
        if not names:
            return None

        fig, ax = plt.subplots(figsize=(3.5, 2.0), dpi=200)
        fig.patch.set_alpha(0.0)
        ax.patch.set_alpha(0.0)

        # Set bar colors: green for positive, red for negative
        colors = ['#34d399' if val >= 0 else '#fb7185' for val in nets]

        # Draw bar chart
        bars = ax.bar(names, nets, color=colors, width=0.5, edgecolor='none')

        # Clean axis lines and set color for tick labels
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('rgba(255,255,255,0.1)')
        ax.spines['bottom'].set_color('rgba(255,255,255,0.1)')
        ax.tick_params(colors='#94a3b8', labelsize=8)

        # Horizontal zero reference line
        ax.axhline(0, color='rgba(255,255,255,0.2)', linewidth=1)

        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0, transparent=True)
        plt.close(fig)
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception as e:
        print("Error generating net standing chart:", e)
        return None

