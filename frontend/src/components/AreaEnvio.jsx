import { useState } from "react";
import { api } from "../api.js";
import { nomeModalidade } from "../formatos.js";

const MODALIDADES = ["video", "video_cirurgico", "audio", "sinais_vitais", "documento"];

// Área de envio de arquivos: escolhe a modalidade, seleciona o arquivo, envia e
// dispara a análise. Mostra a situação de cada passo.
export function AreaEnvio({ pacienteId, aoConcluir }) {
  const [modalidade, setModalidade] = useState("documento");
  const [situacao, setSituacao] = useState(null);
  const [erro, setErro] = useState(null);

  async function enviar(evento) {
    const arquivos = [...evento.target.files];
    evento.target.value = ""; // permite reenviar os mesmos ficheiros
    if (arquivos.length === 0) return;
    setErro(null);
    try {
      setSituacao(`Enviando ${arquivos.map((a) => `"${a.name}"`).join(", ")}…`);
      const envio = await api.enviarArquivo(pacienteId, modalidade, arquivos);
      setSituacao("Analisando…");
      await api.analisarEnvio(envio.id);
      setSituacao(null);
      aoConcluir?.();
    } catch (e) {
      setSituacao(null);
      setErro(e.message);
    }
  }

  return (
    <div className="area-envio">
      <h3>Enviar arquivo</h3>
      <div className="area-envio-linha">
        <label>
          Tipo:
          <select value={modalidade} onChange={(e) => setModalidade(e.target.value)}>
            {MODALIDADES.map((m) => (
              <option key={m} value={m}>
                {nomeModalidade(m)}
              </option>
            ))}
          </select>
        </label>
        <label className="botao-arquivo">
          Escolher arquivo…
          <input type="file" multiple onChange={enviar} disabled={Boolean(situacao)} />
        </label>
      </div>
      {situacao && <p className="aviso-processando">{situacao}</p>}
      {erro && <p className="aviso-erro">{erro}</p>}
    </div>
  );
}
