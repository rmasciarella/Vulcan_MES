import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Providers } from './providers'
import { DashboardLayout } from '@/shared/components/layout/dashboard-layout'
import { GlobalNotifications } from '@/shared/components/notifications/toast-notifications'
import { runStartupEnvCheck } from '@/shared/lib/startup-check'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Vulcan MES - Manufacturing Scheduling',
  description: 'Manufacturing Execution System for production scheduling optimization',
}

// Run a dev-only env check once on module import
runStartupEnvCheck()

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <Providers>
          <DashboardLayout>{children}</DashboardLayout>
          <GlobalNotifications />
        </Providers>
      </body>
    </html>
  )
}
