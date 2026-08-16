import { Route, Routes } from "react-router-dom"
import Topbar from "./components/Topbar"
import EditorPage from "./pages/Editor/EditorPage"
import Welcome from "./pages/Welcome"

export default function App() {
  return (
    <div className="h-screen flex flex-col bg-neutral-900 text-neutral-100">
      <Topbar />
      <main className="flex-1 overflow-hidden">
        <Routes>
          <Route path="/" element={<Welcome />} />
          <Route path="/editor" element={<EditorPage />} />
        </Routes>
      </main>
    </div>
  )
}
