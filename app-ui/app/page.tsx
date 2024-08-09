import * as React from 'react'
import { ModeToggle } from '@/app/ui/model-toggle';

export default function Home() {
  return (
    <main className="dark flex min-h-screen flex-col items-center justify-between p-24">
      <div className='dark w-full h-screen dark:bg-slate-900'>
       Home
       <ModeToggle />
      </div>
    </main>
  );
}
