import { nivelInfo } from "../formatos.js";

// Indicador colorido do nível de risco. `grande` usa a versão de destaque do
// cabeçalho do paciente; o padrão é a bolinha compacta das listas.
export function IndicadorRisco({ nivel, grande = false }) {
  const info = nivelInfo(nivel);
  if (grande) {
    return (
      <div className="indicador-grande" style={{ background: info.fundo, color: info.cor }}>
        <span className="indicador-ponto" style={{ background: info.cor }} />
        <strong>{info.rotulo}</strong>
      </div>
    );
  }
  return (
    <span className="indicador-compacto" title={info.rotulo}>
      <span className="indicador-ponto" style={{ background: info.cor }} />
      {info.rotulo}
    </span>
  );
}
