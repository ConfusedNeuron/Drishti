const CL = {
  paper_bgcolor: "transparent",
  plot_bgcolor: "#0C1118",
  font: { color: "#7D8590", family: "'JetBrains Mono', monospace", size: 10.5 },
  xaxis: { gridcolor: "#21262D", zerolinecolor: "#2D3748", linecolor: "#21262D", tickfont: { size: 10 } },
  yaxis: { gridcolor: "#21262D", zerolinecolor: "#2D3748", linecolor: "#21262D", tickfont: { size: 10 } },
};
const CONF = { responsive: true, displayModeBar: false };

const COLORS = {
  gold:    "#C9A227",
  teal:    "#2EC4B6",
  orange:  "#E07840",
  ok:      "#3FB950",
  danger:  "#F85149",
  muted:   "#7D8590",
  palette: ["#C9A227","#2EC4B6","#E07840","#3FB950","#8B68D8","#EC6C8E"],
};

function fmt(n, d=0) {
  return new Intl.NumberFormat("en-IN", { minimumFractionDigits:d, maximumFractionDigits:d }).format(n);
}
function pct(n) { return (n*100).toFixed(2)+"%" }
