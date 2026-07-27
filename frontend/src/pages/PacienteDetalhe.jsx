import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import { AreaEnvio } from "../components/AreaEnvio.jsx";
import { Evidencia } from "../components/Evidencia.jsx";
import { IndicadorRisco } from "../components/IndicadorRisco.jsx";
import { LinhaDoTempo } from "../components/LinhaDoTempo.jsx";
import { PainelModalidade } from "../components/PainelModalidade.jsx";
import { dataLegivel, nivelInfo, tempoDeMonitoramento } from "../formatos.js";

const MODALIDADES = ["video", "video_cirurgico", "audio", "sinais_vitais", "documento"];

export function PacienteDetalhe() {
  const { id } = useParams();
  const [paciente, setPaciente] = useState(null);
  const [envios, setEnvios] = useState([]);
  const [analises, setAnalises] = useState({});
  const [pontos, setPontos] = useState([]);
  const [alertas, setAlertas] = useState([]);
  const [erro, setErro] = useState(null);
  const [evidencia, setEvidencia] = useState(null); // { id, legenda }

  const carregar = useCallback(async () => {
    try {
      const [p, us, tl, al] = await Promise.all([
        api.obterPaciente(id),
        api.listarEnvios(id),
        api.linhaDoTempo(id),
        api.alertasDoPaciente(id),
      ]);
      setPaciente(p);
      setEnvios(us);
      setPontos(tl);
      setAlertas(al);

      const mapa = {};
      await Promise.all(
        us.map(async (u) => {
          try {
            mapa[u.id] = await api.resultadoDaAnalise(u.id);
          } catch {
            /* envio ainda sem análise */
          }
        })
      );
      setAnalises(mapa);
    } catch (e) {
      setErro(e.message);
    }
  }, [id]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  if (erro) return <p className="aviso-erro">{erro}</p>;
  if (!paciente) return <p className="aviso-processando">Carregando…</p>;

  return (
    <div className="pagina">
      <Link to="/" className="voltar">
        ← Todos os pacientes
      </Link>

      <header className="cabecalho-paciente" style={{ borderColor: nivelInfo(paciente.nivel_atual).cor }}>
        <div>
          <h1>{paciente.nome}</h1>
          <p className="subtitulo">
            Monitoramento iniciado em {dataLegivel(paciente.data_inicio)} (
            {tempoDeMonitoramento(paciente.data_inicio)})
          </p>
          {paciente.observacoes && <p className="observacoes">{paciente.observacoes}</p>}
        </div>
        <IndicadorRisco nivel={paciente.nivel_atual} grande />
      </header>

      <AreaEnvio pacienteId={id} aoConcluir={carregar} />

      <section>
        <h2>Modalidades monitoradas</h2>
        <div className="grade-modalidades">
          {MODALIDADES.map((m) => (
            <PainelModalidade
              key={m}
              modalidade={m}
              envios={envios}
              analises={analises}
              aoAbrirEvidencia={(evId) => setEvidencia({ id: evId, legenda: null })}
            />
          ))}
        </div>
      </section>

      <section>
        <h2>Evolução do risco</h2>
        <LinhaDoTempo
          pontos={pontos}
          aoSelecionarEvento={(evento) =>
            setEvidencia({ id: evento.evidence_id, legenda: evento.summary })
          }
        />
      </section>

      <section>
        <h2>Alertas do paciente</h2>
        {alertas.length === 0 ? (
          <p className="vazio">Nenhum alerta registrado.</p>
        ) : (
          <ul className="lista-alertas">
            {alertas.map((a) => (
              <li key={a.id} className="alerta-item">
                <IndicadorRisco nivel={a.nivel} />
                <div className="alerta-corpo">
                  <p className="alerta-motivo">{a.motivo}</p>
                  <p className="alerta-hora">{dataLegivel(a.criado_em)}</p>
                  {a.referencias.length > 0 && (
                    <div className="alerta-evidencias">
                      {a.referencias.map((ref) => (
                        <button
                          key={ref}
                          className="link-evidencia"
                          onClick={() => setEvidencia({ id: ref, legenda: a.motivo })}
                        >
                          Ver evidência
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {evidencia && (
        <Evidencia
          evidenciaId={evidencia.id}
          legenda={evidencia.legenda}
          aoFechar={() => setEvidencia(null)}
        />
      )}
    </div>
  );
}
