import { useEffect, useState } from "react";
import { api } from "../api.js";

// Painel de detalhe de uma evidência: busca o artefato pela API e o renderiza
// conforme o tipo (imagem, documento PDF ou texto), com uma legenda descritiva.
export function Evidencia({ evidenciaId, legenda, aoFechar }) {
  const [tipo, setTipo] = useState(null);
  const [textoOuUrl, setTextoOuUrl] = useState(null);
  const [erro, setErro] = useState(null);

  useEffect(() => {
    let urlObjeto = null;
    let cancelado = false;
    async function carregar() {
      try {
        const resposta = await fetch(api.urlEvidencia(evidenciaId));
        if (!resposta.ok) throw new Error(`não foi possível carregar a evidência`);
        const contentType = resposta.headers.get("content-type") || "";
        const blob = await resposta.blob();
        if (cancelado) return;
        if (contentType.startsWith("image/")) {
          urlObjeto = URL.createObjectURL(blob);
          setTipo("imagem");
          setTextoOuUrl(urlObjeto);
        } else if (contentType.includes("pdf")) {
          urlObjeto = URL.createObjectURL(blob);
          setTipo("pdf");
          setTextoOuUrl(urlObjeto);
        } else {
          setTipo("texto");
          setTextoOuUrl(await blob.text());
        }
      } catch (e) {
        if (!cancelado) setErro(e.message);
      }
    }
    carregar();
    return () => {
      cancelado = true;
      if (urlObjeto) URL.revokeObjectURL(urlObjeto);
    };
  }, [evidenciaId]);

  return (
    <div className="evidencia-overlay" onClick={aoFechar}>
      <div className="evidencia-caixa" onClick={(e) => e.stopPropagation()}>
        <button className="evidencia-fechar" onClick={aoFechar} aria-label="Fechar">
          ×
        </button>
        {legenda && <p className="evidencia-legenda">{legenda}</p>}
        {erro && <p className="aviso-erro">{erro}</p>}
        {tipo === "imagem" && <img src={textoOuUrl} alt="Evidência" className="evidencia-imagem" />}
        {tipo === "pdf" && (
          <iframe src={textoOuUrl} title="Documento" className="evidencia-pdf" />
        )}
        {tipo === "texto" && <pre className="evidencia-texto">{textoOuUrl}</pre>}
        {!tipo && !erro && <p className="aviso-processando">Carregando evidência…</p>}
      </div>
    </div>
  );
}
