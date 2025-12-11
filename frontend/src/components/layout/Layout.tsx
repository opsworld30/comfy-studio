import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'
import { TooltipProvider } from '@/components/ui/tooltip'

export default function Layout() {
  return (
    <TooltipProvider>
      <div className="flex h-screen bg-gradient-to-br from-background via-background to-background/95">
        <Sidebar />
        <div className="flex flex-1 flex-col overflow-hidden">
          <Header />
          <main className="flex-1 overflow-auto p-6 bg-gradient-to-b from-transparent to-muted/20">
            <div className="max-w-[1600px] mx-auto">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </TooltipProvider>
  )
}
