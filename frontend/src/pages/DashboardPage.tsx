/**
 * DashboardPage - Commander Analytics capabilities.
 */

import { useMemo } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
} from 'chart.js';
import { Bar, Doughnut } from 'react-chartjs-2';
import { format, subDays, isSameDay } from 'date-fns';
import { Layers, CheckCircle2, AlertCircle } from 'lucide-react';
import { useStationSchedule } from '../hooks/useStationSchedule';
import './DashboardPage.css';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
);

export function DashboardPage() {
  const { data: shifts = [], isLoading } = useStationSchedule(new Date());

  const metrics = useMemo(() => {
    let published = 0;
    let drafts = 0;
    const typesCount: Record<string, number> = {};
    const last7Days: Record<string, number> = {};

    // Initialise 7 days
    for (let i = 6; i >= 0; i--) {
      const d = format(subDays(new Date(), i), 'dd/MM');
      last7Days[d] = 0;
    }

    shifts.forEach((shift) => {
      // Counters
      if (shift.status === 'published') published++;
      if (shift.status === 'draft') drafts++;

      // Shift types
      const tName = shift.shift_type_name || 'Desconhecido';
      typesCount[tName] = (typesCount[tName] || 0) + 1;

      // 7 days histogram
      const shiftDateObj = new Date(shift.date);
      for (let i = 0; i <= 6; i++) {
        const checkDay = subDays(new Date(), i);
        if (isSameDay(checkDay, shiftDateObj)) {
          const keyDate = format(checkDay, 'dd/MM');
          if (last7Days[keyDate] !== undefined) {
             last7Days[keyDate] += 1;
          }
        }
      }
    });

    return { published, drafts, typesCount, last7Days };
  }, [shifts]);

  const doughnutData = {
    labels: Object.keys(metrics.typesCount),
    datasets: [
      {
        data: Object.values(metrics.typesCount),
        backgroundColor: [
          '#10b981', // green
          '#3b82f6', // blue
          '#f59e0b', // yellow
          '#8b5cf6', // purple
          '#ec4899', // pink
          '#64748b'  // gray
        ],
        borderWidth: 0,
      },
    ],
  };

  const barData = {
    labels: Object.keys(metrics.last7Days),
    datasets: [
      {
        label: 'Patrulhas Diárias',
        data: Object.values(metrics.last7Days),
        backgroundColor: '#3b82f6',
        borderRadius: 4,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'bottom' as const,
        labels: { color: '#94a3b8' } // text-secondary
      }
    },
    scales: {
      y: { ticks: { color: '#94a3b8' }, grid: { color: '#334155' } },
      x: { ticks: { color: '#94a3b8' }, grid: { display: false } }
    }
  };

  const doughnutOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'right' as const,
        labels: { color: '#94a3b8' }
      }
    },
    cutout: '70%'
  };

  return (
    <div className="page-container animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Centro de Comando</h1>
          <p className="page-subtitle">Métricas e performance laboral do mês corrente.</p>
        </div>
      </div>

      {isLoading ? (
        <div className="page-loader"><div className="spinner" /></div>
      ) : (
        <div className="dashboard-grid">
          {/* Top KPI Cards */}
          <div className="kpi-card">
            <div className="kpi-icon bg-info"><Layers size={24} /></div>
            <div className="kpi-info">
              <span className="kpi-label">Volume Mensal</span>
              <span className="kpi-value">{shifts.length}</span>
            </div>
          </div>
          
          <div className="kpi-card">
            <div className="kpi-icon bg-success"><CheckCircle2 size={24} /></div>
            <div className="kpi-info">
              <span className="kpi-label">Validados</span>
              <span className="kpi-value">{metrics.published}</span>
            </div>
          </div>

          <div className="kpi-card">
            <div className="kpi-icon bg-warning"><AlertCircle size={24} /></div>
            <div className="kpi-info">
              <span className="kpi-label">Rascunhos Pendentes</span>
              <span className="kpi-value">{metrics.drafts}</span>
            </div>
          </div>

          {/* Charts Row */}
          <div className="chart-card span-2">
            <h3 className="chart-title">Distribuição de Tipologia</h3>
            <div className="chart-wrapper">
              <Doughnut data={doughnutData} options={doughnutOptions} />
            </div>
          </div>

          <div className="chart-card span-2">
            <h3 className="chart-title">Trabalho (Últimos 7 dias)</h3>
            <div className="chart-wrapper">
              <Bar data={barData} options={chartOptions} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
