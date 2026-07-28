import { CATEGORIAS_ANVISA, O_QUE_MONITORA, SITUACAO_ENVIO, nomeModalidade, porcentagem } from "../formatos.js";

// Um painel por modalidade: o que monitora, a situação atual e o último achado
// em linguagem clínica. Sem identificadores técnicos na tela.
export function PainelModalidade({ modalidade, envios, analises, aoAbrirEvidencia }) {
  const enviosDaModalidade = envios.filter((e) => e.modalidade === modalidade);
  const ultimoEnvio = enviosDaModalidade[enviosDaModalidade.length - 1];
  const ultimaAnalise = ultimoEnvio ? analises[ultimoEnvio.id] : undefined;

  let situacao = "Nenhum arquivo enviado ainda.";
  if (ultimoEnvio) {
    situacao = SITUACAO_ENVIO[ultimoEnvio.situacao] || ultimoEnvio.situacao;
  }

  const temAchado = ultimaAnalise && ultimaAnalise.pontuacao > 0;
  const detalhes = ultimaAnalise?.detalhes || {};
  const temAnvisa = detalhes.control_category || detalhes.active_ingredient;

  return (
    <div className={`painel-modalidade ${temAchado ? "com-achado" : ""}`}>
      <h4>{nomeModalidade(modalidade)}</h4>
      <p className="painel-descricao">{O_QUE_MONITORA[modalidade]}</p>
      <p className="painel-situacao">
        <span className="rotulo">Situação:</span> {situacao}
      </p>
      {ultimaAnalise ? (
        <div className="painel-achado">
          <p>{ultimaAnalise.resumo}</p>
          {ultimaAnalise.pontuacao != null && (
            <p className="painel-confianca">Relevância: {porcentagem(ultimaAnalise.pontuacao)}</p>
          )}
          {/* Info ANVISA para prescrições */}
          {temAnvisa && (
            <div className="painel-anvisa">
              {detalhes.active_ingredient && (
                <p className="anvisa-info">Princípio ativo: <strong>{detalhes.active_ingredient}</strong></p>
              )}
              {detalhes.control_category && (
                <p className={`anvisa-info ${detalhes.is_controlled ? "controlado" : ""}`}>
                  {CATEGORIAS_ANVISA[detalhes.control_category] || detalhes.control_category}
                </p>
              )}
              {detalhes.reference_dose && (
                <p className="anvisa-info">Dose referência: {detalhes.reference_dose}</p>
              )}
              {detalhes.source && (
                <p className="anvisa-fonte">Fonte: {detalhes.source}</p>
              )}
            </div>
          )}
          {ultimaAnalise.evidencia_id && (
            <button className="link-evidencia" onClick={() => aoAbrirEvidencia(ultimaAnalise.evidencia_id)}>
              Ver evidência
            </button>
          )}
        </div>
      ) : (
        <p className="painel-achado sem-achado">Sem achados até o momento.</p>
      )}
    </div>
  );
}
