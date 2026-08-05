import { Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Board } from './screens/Board'
import { Composer } from './screens/Composer'
import { Config } from './screens/Config'
import { Cota } from './screens/Cota'
import { Diff } from './screens/Diff'
import { Fila } from './screens/Fila'
import { Projeto } from './screens/Projeto'
import { Run } from './screens/Run'

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Board />} />
        <Route path="projetos/:id" element={<Projeto />} />
        <Route path="composer" element={<Composer />} />
        <Route path="runs/:id" element={<Run />} />
        <Route path="runs/:id/diff" element={<Diff />} />
        <Route path="fila" element={<Fila />} />
        <Route path="cota" element={<Cota />} />
        <Route path="config" element={<Config />} />
      </Route>
    </Routes>
  )
}

export default App
