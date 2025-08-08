'use client'

import * as React from 'react'
import { Check } from 'lucide-react'
import { cn } from '@/shared/lib/utils'

export interface CheckboxProps extends React.InputHTMLAttributes<HTMLInputElement> {
  indeterminate?: boolean
  onCheckedChange?: (checked: boolean) => void
}

const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, indeterminate, onCheckedChange, ...props }, ref) => {
    const inputRef = React.useRef<HTMLInputElement>(null)

    React.useImperativeHandle(ref, () => inputRef.current!)

    React.useEffect(() => {
      if (inputRef.current) {
        inputRef.current.indeterminate = !!indeterminate
      }
    }, [indeterminate])

    return (
      <div className="relative">
        <input
          type="checkbox"
          className={cn(
            'peer h-4 w-4 shrink-0 rounded-sm border border-primary ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground',
            className,
          )}
          ref={inputRef}
          onChange={(e) => onCheckedChange?.(e.target.checked)}
          {...props}
        />
        {(props.checked || indeterminate) && (
          <Check
            className={cn(
              'pointer-events-none absolute inset-0 h-4 w-4 text-primary-foreground',
              indeterminate && 'opacity-50',
            )}
          />
        )}
      </div>
    )
  },
)
Checkbox.displayName = 'Checkbox'

export { Checkbox }
