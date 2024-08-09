import { Providers } from '@/app/dashboard-old/providers'
import SimpleSidebar from '@/app/ui/sidebar';

export default function Layout({ children }: { children: React.ReactNode }) {
    return (
        <main>
            <Providers>
                <div className="flex h-screen flex-row md:overflow-hidden">
                    <div className="h-full w-64 flex-none">
                    <SimpleSidebar />
                    </div>
                    <div className="flex-grow p-6 overflow-y-auto p-12">{children}</div>
                </div>
            </Providers>
        </main>
    );
  }