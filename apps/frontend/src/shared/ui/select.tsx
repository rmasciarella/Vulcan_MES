'use client'

import * as React from 'react'
import { ChevronDown, Check } from 'lucide-react'
import { cn } from '@/shared/lib/utils'

interface SelectContextValue {
  value: string
  onValueChange: (value: string) => void
  open: boolean
  onOpenChange: (open: boolean) => void
}

const SelectContext = React.createContext<SelectContextValue | null>(null)

const useSelect = () => {
  const context = React.useContext(SelectContext)
  if (!context) {
    throw new Error('Select compound components must be used within Select')
  }
  return context
}

interface SelectProps {
  value?: string
  onValueChange?: (value: string) => void
  children: React.ReactNode
  defaultValue?: string
}

export function Select({
  value: controlledValue,
  onValueChange,
  children,
  defaultValue = '',
}: SelectProps) {
  const [uncontrolledValue, setUncontrolledValue] = React.useState(defaultValue)
  const [open, setOpen] = React.useState(false)

  const value = controlledValue ?? uncontrolledValue
  const handleValueChange = React.useCallback(
    (newValue: string) => {
      if (controlledValue === undefined) {
        setUncontrolledValue(newValue)
      }
      onValueChange?.(newValue)
      setOpen(false)
    },
    [controlledValue, onValueChange],
  )

  return (
    <SelectContext.Provider
      value={{
        value,
        onValueChange: handleValueChange,
        open,
        onOpenChange: setOpen,
      }}
    >
      <div className="relative">{children}</div>
    </SelectContext.Provider>
  )
}

interface SelectTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  className?: string
  children: React.ReactNode
  placeholder?: string
}

export function SelectTrigger({
  className,
  children,
  placeholder: _placeholder,
  ...props
}: SelectTriggerProps) {
  const { open, onOpenChange } = useSelect()

  return (
    <button
      className={cn(
        'flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      onClick={() => onOpenChange(!open)}
      {...props}
    >
      {children}
      <ChevronDown
        className={cn('h-4 w-4 opacity-50 transition-transform', open && 'rotate-180')}
      />
    </button>
  )
}

interface SelectValueProps {
  placeholder?: string
}

export function SelectValue({ placeholder }: SelectValueProps) {
  const { value } = useSelect()
  return <span>{value || placeholder}</span>
}

interface SelectContentProps {
  className?: string
  children: React.ReactNode
}

export function SelectContent({ className, children }: SelectContentProps) {
  const { open } = useSelect()

  if (!open) return null

  return (
    <div
      className={cn(
        'absolute top-full z-50 mt-1 min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md animate-in fade-in-0 zoom-in-95',
        className,
      )}
    >
      <div className="max-h-60 overflow-y-auto">{children}</div>
    </div>
  )
}

interface SelectItemProps {
  value: string
  className?: string
  children: React.ReactNode
}

export function SelectItem({ value, className, children }: SelectItemProps) {
  const { value: selectedValue, onValueChange } = useSelect()
  const isSelected = selectedValue === value

  return (
    <div
      className={cn(
        'relative flex w-full cursor-pointer select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground',
        isSelected && 'bg-accent',
        className,
      )}
      onClick={() => onValueChange(value)}
    >
      <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
        {isSelected && <Check className="h-4 w-4" />}
      </span>
      {children}
    </div>
  )
}

export function SelectSeparator({ className }: { className?: string }) {
  return <div className={cn('-mx-1 my-1 h-px bg-muted', className)} />
}
