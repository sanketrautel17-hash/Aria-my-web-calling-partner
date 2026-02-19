// ── App.tsx ────────────────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Sidebar } from '@/components/Sidebar'
import { CallScreen } from '@/components/CallScreen'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000 } },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="flex h-screen bg-[#07080f] text-[#f0f2ff] overflow-hidden">
        {/* Sidebar */}
        <Sidebar />

        {/* Main content */}
        <main className="flex-1 flex flex-col overflow-hidden relative">
          {/* Subtle background radial glow */}
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              background:
                'radial-gradient(ellipse 70% 50% at 50% 20%, rgba(124,58,237,0.07) 0%, transparent 70%)',
            }}
          />
          <CallScreen />
        </main>
      </div>
    </QueryClientProvider>
  )
}
