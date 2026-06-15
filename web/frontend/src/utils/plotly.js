export const DARK_LAYOUT = {
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  font: { color: '#a1a1aa', family: 'Inter, system-ui, sans-serif', size: 12 },
  margin: { t: 40, r: 20, b: 40, l: 40 },
  xaxis: {
    gridcolor: 'rgba(161,161,170,0.1)',
    zerolinecolor: 'rgba(161,161,170,0.2)',
  },
  yaxis: {
    gridcolor: 'rgba(161,161,170,0.1)',
    zerolinecolor: 'rgba(161,161,170,0.2)',
  },
}

export const PLOTLY_CONFIG = {
  displayModeBar: false,
  responsive: true,
}

export const RADAR_LAYOUT = {
  ...DARK_LAYOUT,
  polar: {
    bgcolor: 'rgba(0,0,0,0)',
    radialaxis: {
      visible: true,
      range: [0, 10],
      gridcolor: 'rgba(161,161,170,0.15)',
      tickfont: { size: 10, color: '#71717a' },
    },
    angularaxis: {
      gridcolor: 'rgba(161,161,170,0.15)',
      tickfont: { size: 11, color: '#d4d4d8' },
    },
  },
  showlegend: false,
  margin: { t: 30, r: 60, b: 30, l: 60 },
}
