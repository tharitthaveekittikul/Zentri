"use client"

import * as React from "react"
import { format, parse, isValid } from "date-fns"
import { CalendarIcon, X } from "lucide-react"
import type { DateRange } from "react-day-picker"
import { cn } from "@/lib/utils"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover"

interface DateRangePickerProps {
  from?: string | null
  to?: string | null
  onChange: (range: { from: string | null; to: string | null }) => void
  placeholder?: string
  className?: string
}

function parseDate(value?: string | null): Date | undefined {
  if (!value) return undefined
  const d = parse(value, "yyyy-MM-dd", new Date())
  return isValid(d) ? d : undefined
}

export function DateRangePicker({
  from,
  to,
  onChange,
  placeholder = "Pick date range",
  className,
}: DateRangePickerProps) {
  const [open, setOpen] = React.useState(false)

  const fromDate = parseDate(from)
  const toDate = parseDate(to)
  const range: DateRange | undefined = fromDate ? { from: fromDate, to: toDate } : undefined
  const hasRange = Boolean(fromDate || toDate)

  function handleSelect(selected: DateRange | undefined) {
    const newFrom = selected?.from ? format(selected.from, "yyyy-MM-dd") : null
    const newTo = selected?.to ? format(selected.to, "yyyy-MM-dd") : null
    onChange({ from: newFrom, to: newTo })
    if (selected?.from && selected?.to) setOpen(false)
  }

  function handleClear(e: React.MouseEvent) {
    e.stopPropagation()
    onChange({ from: null, to: null })
  }

  function label() {
    if (!fromDate && !toDate) return null
    if (fromDate && toDate) {
      const sameYear = fromDate.getFullYear() === toDate.getFullYear()
      return `${format(fromDate, sameYear ? "MMM d" : "MMM d, yyyy")} – ${format(toDate, "MMM d, yyyy")}`
    }
    if (fromDate) return `From ${format(fromDate, "MMM d, yyyy")}`
    return `To ${format(toDate!, "MMM d, yyyy")}`
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        className={cn(
          "flex h-9 items-center gap-2 rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm whitespace-nowrap transition-colors outline-none hover:bg-accent hover:text-accent-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
          !hasRange && "text-muted-foreground",
          className
        )}
      >
        <CalendarIcon className="size-4 shrink-0 opacity-60" />
        <span>{label() ?? placeholder}</span>
        {hasRange && (
          <span
            role="button"
            onClick={handleClear}
            className="ml-auto rounded-sm p-0.5 hover:text-foreground"
          >
            <X className="size-3" />
          </span>
        )}
      </PopoverTrigger>
      <PopoverContent>
        <Calendar
          mode="range"
          selected={range}
          onSelect={handleSelect}
          numberOfMonths={2}
          captionLayout="dropdown"
          fromYear={2000}
          toYear={new Date().getFullYear() + 1}
        />
      </PopoverContent>
    </Popover>
  )
}
