import React from 'react'

type Variant = 'default' | 'outline' | 'ghost' | 'destructive'

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  size?: 'sm' | 'md' | 'lg'
}

export function Button({ className = '', variant = 'default', size = 'md', ...props }: ButtonProps) {
  const base = 'inline-flex items-center justify-center rounded-md font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2'
  const variants: Record<Variant, string> = {
    default: 'bg-gray-900 text-white hover:bg-gray-800 focus:ring-gray-400',
    outline: 'border border-gray-300 bg-white text-gray-900 hover:bg-gray-50 focus:ring-gray-300',
    ghost: 'bg-transparent text-gray-900 hover:bg-gray-100 focus:ring-gray-300',
    destructive: 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-400',
  }
  const sizes = {
    sm: 'h-8 px-2 text-xs',
    md: 'h-9 px-3 text-sm',
    lg: 'h-10 px-4 text-base',
  }
  return <button className={`${base} ${variants[variant]} ${sizes[size]} ${className}`} {...props} />
}
