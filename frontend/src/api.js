// Cliente HTTP da API. Em desenvolvimento, o Vite faz proxy destas rotas para o
// backend (ver vite.config.js), então usamos caminhos relativos.

async function pedir(caminho, opcoes) {
  const resposta = await fetch(caminho, opcoes);
  if (!resposta.ok) {
    let detalhe = `erro ${resposta.status}`;
    try {
      const corpo = await resposta.json();
      if (corpo.detail) detalhe = corpo.detail;
    } catch {
      /* resposta sem corpo JSON */
    }
    throw new Error(detalhe);
  }
  if (resposta.status === 204) return null;
  return resposta.json();
}

export const api = {
  listarPacientes: () => pedir("/patients"),
  criarPaciente: (dados) =>
    pedir("/patients", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dados),
    }),
  obterPaciente: (id) => pedir(`/patients/${id}`),
  removerPaciente: (id) => pedir(`/patients/${id}`, { method: "DELETE" }),

  listarEnvios: (id) => pedir(`/patients/${id}/uploads`),
  enviarArquivo: (id, modalidade, arquivos) => {
    const form = new FormData();
    const lista = Array.isArray(arquivos) ? arquivos : [arquivos];
    for (const f of lista) {
      form.append("arquivos", f);
    }
    return pedir(`/patients/${id}/uploads?modalidade=${modalidade}`, {
      method: "POST",
      body: form,
    });
  },

  analisarEnvio: (uploadId) => pedir(`/uploads/${uploadId}/analyze`, { method: "POST" }),
  resultadoDaAnalise: (uploadId) => pedir(`/uploads/${uploadId}/analysis`),

  linhaDoTempo: (id) => pedir(`/patients/${id}/timeline`),
  alertasDoPaciente: (id) => pedir(`/patients/${id}/alerts`),
  todosOsAlertas: () => pedir("/alerts"),

  urlEvidencia: (evidenciaId) => `/evidence/${evidenciaId}`,
};
