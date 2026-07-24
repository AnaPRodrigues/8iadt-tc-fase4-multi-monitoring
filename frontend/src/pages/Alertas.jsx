import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { IndicadorRisco } from "../components/IndicadorRisco.jsx";
import { dataLegivel, nivelInfo } from "../formatos.js";

const NIVEIS_FILTRO = ["todos", "vermelho", "amarelo", "verde"];

export function Alertas() {
  const [alertas, setAlertas] = useState([]);
  const [pacientes, setPacientes] = useState({});
  const [erro, setErro] = useState(null);
  const [filtroPaciente, setFiltroPaciente] = useState("todos");
  const [filtroNivel, setFiltroNivel] = useState("todos");

  useEffect(() => {
    async function carregar() {
      try {
        const [als, ps] = await Promise.all([api.todosOsAlertas(), api.listarPacientes()]);
        setAlertas(als);
        setPacientes(Object.fromEntries(ps.map((p) => [p.id, p.nome])));
      } catch (e) {
        setErro(e.message);
      }
    }
    carregar();
  }, []);

  const filtrados = useMemo(
    () =>
      alertas.filter(
        (a) =>
          (filtroPaciente === "todos" || a.paciente_id === filtroPaciente) &&
          (filtroNivel === "todos" || a.nivel === filtroNivel)
      ),
    [alertas, filtroPaciente, filtroNivel]
  );

  return (
    <div className="pagina">
      <h1>Todos os alertas</h1>

      <div className="filtros">
        <label>
          Paciente:
          <select value={filtroPaciente} onChange={(e) => setFiltroPaciente(e.target.value)}>
            <option value="todos">Todos</option>
            {Object.entries(pacientes).map(([id, nome]) => (
              <option key={id} value={id}>
                {nome}
              </option>
            ))}
          </select>
        </label>
        <label>
          Nível:
          <select value={filtroNivel} onChange={(e) => setFiltroNivel(e.target.value)}>
            {NIVEIS_FILTRO.map((n) => (
              <option key={n} value={n}>
                {n === "todos" ? "Todos" : nivelInfo(n).rotulo}
              </option>
            ))}
          </select>
        </label>
      </div>

      {erro && <p className="aviso-erro">{erro}</p>}
      {filtrados.length === 0 ? (
        <p className="vazio">Nenhum alerta para os filtros escolhidos.</p>
      ) : (
        <ul className="lista-alertas">
          {filtrados.map((a) => (
            <li key={a.id} className="alerta-item">
              <IndicadorRisco nivel={a.nivel} />
              <div className="alerta-corpo">
                <p className="alerta-motivo">{a.motivo}</p>
                <p className="alerta-hora">
                  <Link to={`/pacientes/${a.paciente_id}`}>
                    {pacientes[a.paciente_id] || a.paciente_id}
                  </Link>{" "}
                  — {dataLegivel(a.criado_em)}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
