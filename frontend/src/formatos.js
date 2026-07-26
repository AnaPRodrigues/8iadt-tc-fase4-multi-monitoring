// Rótulos e formatações voltados ao usuário. Nada de identificador técnico ou
// número com muitas casas na tela.

// Nomes de modalidade legíveis (aceita tanto os nomes do envio quanto os do motor
// de fusão, que usa "prescription"/"vitals").
const NOMES_MODALIDADE = {
  video: "Vídeo — movimentação",
  video_cirurgico: "Vídeo — cirurgia",
  audio: "Áudio",
  sinais_vitais: "Sinais vitais",
  documento: "Prescrições",
  vitals: "Sinais vitais",
  prescription: "Prescrições",
};

export function nomeModalidade(modalidade) {
  return NOMES_MODALIDADE[modalidade] || modalidade;
}

// O que cada painel monitora (texto explicativo para quem não conhece o sistema).
export const O_QUE_MONITORA = {
  video: "Quedas e padrões de movimentação do paciente.",
  video_cirurgico: "Estruturas anatómicas críticas em vídeo cirúrgico.",
  audio: "Alterações respiratórias, termos críticos e fadiga vocal na ausculta/consulta.",
  sinais_vitais: "Anomalias na série de sinais vitais ao longo do tempo.",
  documento: "Doses fora da faixa segura ou mudanças abruptas na prescrição.",
};

export const NIVEIS = {
  verde: { rotulo: "Estável", cor: "#1a7f4b", fundo: "#e6f4ec" },
  amarelo: { rotulo: "Atenção", cor: "#9a6a00", fundo: "#fbf3d9" },
  vermelho: { rotulo: "Alerta", cor: "#b3261e", fundo: "#fbe6e4" },
};

export function nivelInfo(nivel) {
  return NIVEIS[nivel] || NIVEIS.verde;
}

export const SITUACAO_ENVIO = {
  recebido: "Recebido",
  processando: "Processando…",
  concluido: "Concluído",
  erro: "Erro",
};

// Pontuação de risco como porcentagem inteira (0–100%).
export function porcentagem(valor) {
  if (valor === null || valor === undefined) return "—";
  return `${Math.round(valor * 100)}%`;
}

// Segundos desde o início do monitoramento -> tempo legível ("12 min", "1 h 05 min").
export function tempoLegivel(segundos) {
  const s = Math.max(0, Math.round(segundos));
  const min = Math.floor(s / 60);
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60);
  const restoMin = min % 60;
  return `${h} h ${String(restoMin).padStart(2, "0")} min`;
}

// Data/hora ISO -> formato local legível.
export function dataLegivel(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// Tempo de monitoramento desde a data de início até agora.
export function tempoDeMonitoramento(dataInicioIso) {
  const inicio = new Date(dataInicioIso);
  if (Number.isNaN(inicio.getTime())) return "—";
  const dias = Math.floor((Date.now() - inicio.getTime()) / 86400000);
  if (dias <= 0) return "iniciado hoje";
  if (dias === 1) return "há 1 dia";
  return `há ${dias} dias`;
}
