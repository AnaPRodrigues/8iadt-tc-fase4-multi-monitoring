import { NavLink, Route, Routes } from "react-router-dom";
import { Alertas } from "./pages/Alertas.jsx";
import { PacienteDetalhe } from "./pages/PacienteDetalhe.jsx";
import { Pacientes } from "./pages/Pacientes.jsx";

export function App() {
  return (
    <div className="app">
      <nav className="barra-nav">
        <span className="marca">🩺 Monitoramento Multimodal</span>
        <div className="nav-links">
          <NavLink to="/" end>
            Pacientes
          </NavLink>
          <NavLink to="/alertas">Alertas</NavLink>
        </div>
      </nav>
      <main className="conteudo">
        <Routes>
          <Route path="/" element={<Pacientes />} />
          <Route path="/pacientes/:id" element={<PacienteDetalhe />} />
          <Route path="/alertas" element={<Alertas />} />
        </Routes>
      </main>
    </div>
  );
}
