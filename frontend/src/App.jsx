import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from './lib/queryClient'
import Layout from './components/Layout'
import Feed from './pages/Feed'
import MessageReview from './pages/MessageReview'
import Queue from './pages/Queue'
import Tracker from './pages/Tracker'
import Settings from './pages/Settings'

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Feed />} />
            <Route path="/review/:id" element={<MessageReview />} />
            <Route path="/queue" element={<Queue />} />
            <Route path="/tracker" element={<Tracker />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
