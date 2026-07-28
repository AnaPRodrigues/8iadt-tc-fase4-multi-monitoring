import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { nivelInfo, nomeModalidade, porcentagem, tempoLegivel } from "../formatos.js";

// Linha do tempo da pontuação de risco. Eixo horizontal em tempo legível desde o
// início do monitoramento; linhas de atenção (30%) e alerta (70%); um marcador
// maior nos instantes em que alguma modalidade gerou um evento (clicável).
const ATENCAO = 0.15;
const ALERTA = 0.35;

function DicaPersonalizada({ active, payload }) {
  if (!active || !payload || !payload.length) return null;
  const ponto = payload[0].payload;
  return (
    <div className="dica-timeline">
      <strong>{tempoLegivel(ponto.t)}</strong>
      <div>Risco: {porcentagem(ponto.score)}</div>
      <div style={{ color: nivelInfo(ponto.nivel).cor }}>{nivelInfo(ponto.nivel).rotulo}</div>
      {ponto.eventos.map((e, i) => (
        <div key={i} className="dica-evento">
          • {nomeModalidade(e.modality)}: {e.summary}
        </div>
      ))}
    </div>
  );
}

export function LinhaDoTempo({ pontos, aoSelecionarEvento }) {
  if (!pontos.length) {
    return <p className="vazio">Sem dados suficientes para a linha do tempo.</p>;
  }

  const dados = pontos.map((p) => ({
    t: p.t,
    minuto: +(p.t / 60).toFixed(1),
    score: p.score,
    nivel: p.level,
    eventos: p.contributing_events,
  }));

  function PontoClicavel(props) {
    const { cx, cy, payload } = props;
    const temEvento = payload.eventos && payload.eventos.length > 0;
    if (!temEvento) return null;
    return (
      <circle
        cx={cx}
        cy={cy}
        r={7}
        fill={nivelInfo(payload.nivel).cor}
        stroke="#fff"
        strokeWidth={2}
        style={{ cursor: "pointer" }}
        onClick={() => aoSelecionarEvento(payload.eventos[0])}
      />
    );
  }

  return (
    <div className="timeline">
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={dados} margin={{ top: 12, right: 24, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis
            dataKey="minuto"
            unit=" min"
            type="number"
            domain={[0, "dataMax"]}
            tick={{ fontSize: 12 }}
          />
          <YAxis
            domain={[0, 1]}
            tickFormatter={(v) => `${Math.round(v * 100)}%`}
            tick={{ fontSize: 12 }}
          />
          <Tooltip content={<DicaPersonalizada />} />
          <ReferenceLine y={ATENCAO} stroke="#9a6a00" strokeDasharray="4 4" label={{ value: "Atenção", position: "right", fontSize: 11, fill: "#9a6a00" }} />
          <ReferenceLine y={ALERTA} stroke="#b3261e" strokeDasharray="4 4" label={{ value: "Alerta", position: "right", fontSize: 11, fill: "#b3261e" }} />
          <Line
            type="monotone"
            dataKey="score"
            stroke="#2b6cb0"
            strokeWidth={2}
            dot={<PontoClicavel />}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
      <p className="legenda-timeline">
        Clique em um marcador para ver a evidência do evento naquele instante.
      </p>
    </div>
  );
}
