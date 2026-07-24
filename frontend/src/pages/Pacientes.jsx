import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { IndicadorRisco } from "../components/IndicadorRisco.jsx";
import { dataLegivel } from "../formatos.js";

export function Pacientes() {
  const [pacientes, setPacientes] = useState([]);
  const [nome, setNome] = useState("");
  const [observacoes, setObservacoes] = useState("");
  const [erro, setErro] = useState(null);
  const [carregando, setCarregando] = useState(true);

  async function recarregar() {
    try {
      setPacientes(await api.listarPacientes());
    } catch (e) {
      setErro(e.message);
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    recarregar();
  }, []);

  async function cadastrar(evento) {
    evento.preventDefault();
    setErro(null);
    try {
      await api.criarPaciente({ nome, observacoes: observacoes || null });
      setNome("");
      setObservacoes("");
      recarregar();
    } catch (e) {
      setErro(e.message);
    }
  }

  async function remover(id) {
    if (!confirm("Remover este paciente e todos os seus dados?")) return;
    try {
      await api.removerPaciente(id);
      recarregar();
    } catch (e) {
      setErro(e.message);
    }
  }

  return (
    <div className="pagina">
      <h1>Pacientes monitorados</h1>

      <form className="cartao form-paciente" onSubmit={cadastrar}>
        <h3>Cadastrar paciente</h3>
        <input
          placeholder="Nome ou identificação"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          required
        />
        <input
          placeholder="Observações (opcional)"
          value={observacoes}
          onChange={(e) => setObservacoes(e.target.value)}
        />
        <button type="submit">Cadastrar</button>
      </form>

      {erro && <p className="aviso-erro">{erro}</p>}
      {carregando ? (
        <p className="aviso-processando">Carregando…</p>
      ) : pacientes.length === 0 ? (
        <p className="vazio">Nenhum paciente cadastrado ainda.</p>
      ) : (
        <table className="tabela">
          <thead>
            <tr>
              <th>Paciente</th>
              <th>Início do monitoramento</th>
              <th>Situação atual</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {pacientes.map((p) => (
              <tr key={p.id}>
                <td>
                  <Link to={`/pacientes/${p.id}`} className="link-paciente">
                    {p.nome}
                  </Link>
                </td>
                <td>{dataLegivel(p.data_inicio)}</td>
                <td>
                  <IndicadorRisco nivel={p.nivel_atual} />
                </td>
                <td>
                  <button className="botao-remover" onClick={() => remover(p.id)}>
                    Remover
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
