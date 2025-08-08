import React from 'react'
import { cn } from '@/shared/lib/utils'

type Variant = 'default' | 'secondary' | 'outline' | 'destructive'

type BadgeProps = React.HTMLAttributes<HTMLSpanElement> & {
  variant?: Variant
}

export function Badge({ children, className, variant = 'default', ...rest }: BadgeProps) {
  const base = 'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium'
  const variants: Record<Variant, string> = {
    default: 'bg-gray-100 text-gray-700',
    secondary: 'bg-blue-100 text-blue-800',
    outline: 'border border-gray-300 bg-white text-gray-700',
    destructive: 'bg-red-100 text-red-800',
  }
  return (
    <span className={cn(base, variants[variant], className)} {...rest}>
      {children}
    </span>
  )
}
