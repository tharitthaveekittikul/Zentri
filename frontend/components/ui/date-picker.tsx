"use client"

import * as React from "react"
import { format, parse, isValid } from "date-fns"
import { CalendarIcon } from "lucide-react"
import type { DayPickerProps } from "react-day-picker"
import { cn } from "@/lib/utils"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover"

interface DatePickerProps {
  value?: string
  onChange: (date: string) => void
  placeholder?: string
  className?: string
  captionLayout?: DayPickerProps["captionLayout"]
}

export function DatePicker({
  value,
  onChange,
  placeholder = "Pick a date",
  className,
  captionLayout,
}: DatePickerProps) {
  const [open, setOpen] = React.useState(false)

  const selected = value ? parse(value, "yyyy-MM-dd", new Date()) : undefined
  const valid = selected !== undefined && isValid(selected)

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        className={cn(
          "flex h-9 w-full items-center gap-2 rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm whitespace-nowrap transition-colors outline-none hover:bg-accent hover:text-accent-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50",
          !valid && "text-muted-foreground",
          className
        )}
      >
        <CalendarIcon className="size-4 shrink-0 opacity-60" />
        <span>{valid ? format(selected!, "MMM d, yyyy") : placeholder}</span>
      </PopoverTrigger>
      <PopoverContent>
        <Calendar
          mode="single"
          selected={valid ? selected : undefined}
          onSelect={(date) => {
            if (date) {
              onChange(format(date, "yyyy-MM-dd"))
              setOpen(false)
            }
          }}
          captionLayout={captionLayout}
        />
      </PopoverContent>
    </Popover>
  )
}
