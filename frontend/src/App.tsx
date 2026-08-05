import { Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Board } from './screens/Board'
import { Config } from './screens/Config'
import { Cota } from './screens/Cota'
import { Fila } from './screens/Fila'
import { Projeto } from './screens/Projeto'

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Board />} />
        <Route path="projetos/:id" element={<Projeto />} />
        <Route path="fila" element={<Fila />} />
        <Route path="cota" element={<Cota />} />
        <Route path="config" element={<Config />} />
      </Route>
    </Routes>
  )
}

export default App
