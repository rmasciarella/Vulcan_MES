import React from 'react'
import { cn } from '@/shared/lib/utils'

type Variant = 'default' | 'destructive'

type AlertProps = {
  children: React.ReactNode
  className?: string
  variant?: Variant
}

export function Alert({ children, className, variant = 'default' }: AlertProps) {
  const base = 'rounded-md border p-3'
  const variants: Record<Variant, string> = {
    default: 'border-gray-300 bg-gray-50 text-gray-800',
    destructive: 'border-red-300 bg-red-50 text-red-800',
  }
  return <div className={cn(base, variants[variant], className)}>{children}</div>
}

type AlertDescriptionProps = {
  children: React.ReactNode
  className?: string
}

export function AlertDescription({ children, className }: AlertDescriptionProps) {
  return <div className={cn('text-sm', className)}>{children}</div>
}
