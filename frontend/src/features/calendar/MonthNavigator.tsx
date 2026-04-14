/**
 * MonthNavigator — header with month navigation and view toggle.
 */

import { ChevronLeft, ChevronRight, Calendar } from 'lucide-react';
import { format, addMonths, subMonths } from 'date-fns';
import { pt } from 'date-fns/locale';
import './MonthNavigator.css';

interface MonthNavigatorProps {
  currentMonth: Date;
  onMonthChange: (date: Date) => void;
  title?: string;
  children?: React.ReactNode;
}

export function MonthNavigator({
  currentMonth,
  onMonthChange,
  title,
  children,
}: MonthNavigatorProps) {
  const goToPrev = () => onMonthChange(subMonths(currentMonth, 1));
  const goToNext = () => onMonthChange(addMonths(currentMonth, 1));
  const goToToday = () => onMonthChange(new Date());

  const monthLabel = format(currentMonth, 'MMMM yyyy', { locale: pt });

  return (
    <div className="month-nav">
      <div className="month-nav-left">
        {title && <h1 className="month-nav-title">{title}</h1>}
      </div>

      <div className="month-nav-center">
        <button
          className="btn btn-ghost btn-icon"
          onClick={goToPrev}
          title="Mês anterior"
        >
          <ChevronLeft size={20} />
        </button>
        <span className="month-nav-label">
          {monthLabel}
        </span>
        <button
          className="btn btn-ghost btn-icon"
          onClick={goToNext}
          title="Mês seguinte"
        >
          <ChevronRight size={20} />
        </button>
        <button
          className="btn btn-ghost btn-sm month-nav-today"
          onClick={goToToday}
        >
          <Calendar size={14} />
          Hoje
        </button>
      </div>

      <div className="month-nav-right">
        {children}
      </div>
    </div>
  );
}
