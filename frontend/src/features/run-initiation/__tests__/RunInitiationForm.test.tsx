import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import RunInitiationForm from '../RunInitiationForm';

vi.mock('../../../services/bmadService', () => ({
  createRun: vi.fn(),
  submitRunClarifications: vi.fn(),
  fetchRun: vi.fn(),
  applyPhaseCorrection: vi.fn(),
}));

vi.mock('../../run-observability/RunTimeline', () => ({
  default: () => <div data-testid="run-timeline" />,
}));

import { applyPhaseCorrection, createRun, fetchRun } from '../../../services/bmadService';

const buildRun = (overrides: Record<string, unknown> = {}) => ({
  id: 99,
  status: 'awaiting-approval',
  original_input: 'Create todo API',
  resolved_input_context: 'resolved context',
  context_version: 1,
  context_events: [],
  phase_statuses: { code: 'awaiting-approval' },
  phase_status_badges: { 'awaiting-approval': 'awaiting-approval' },
  current_phase_proposal: {
    phase: 'code',
    revision: 1,
    verification: { overall: 'failed', checks: [] },
    correction_proposal: {
      mismatch_id: 'code-todo-api-ui',
      source_check_id: 'code-todo-api-ui',
      recommended_change_target: 'frontend todo-create request payload',
      patch_guidance: 'Include completed field',
    },
  },
  ...overrides,
});

describe('RunInitiationForm correction apply controls', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  it('shows apply correction button only when correction proposal exists', async () => {
    vi.mocked(createRun).mockResolvedValue({
      run: buildRun(),
      validation: { is_complete: true, missing_items: [], clarification_questions: [] },
    });

    render(<RunInitiationForm />);

    fireEvent.change(screen.getByPlaceholderText(/Enter free-text API specification/i), {
      target: { value: 'Create todo api' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Initiate BMAD Run/i }));

    expect(await screen.findByRole('button', { name: /Apply correction/i })).toBeInTheDocument();

    vi.mocked(createRun).mockResolvedValueOnce({
      run: buildRun({
        current_phase_proposal: {
          phase: 'code',
          revision: 1,
          verification: { overall: 'passed', checks: [] },
        },
      }),
      validation: { is_complete: true, missing_items: [], clarification_questions: [] },
    });

    fireEvent.change(screen.getByPlaceholderText(/Enter free-text API specification/i), {
      target: { value: 'Create todo api again' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Initiate BMAD Run/i }));

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Apply correction/i })).not.toBeInTheDocument();
    });
  });

  it('disables apply button while request is in progress', async () => {
    vi.mocked(createRun).mockResolvedValue({
      run: buildRun(),
      validation: { is_complete: true, missing_items: [], clarification_questions: [] },
    });

    let resolveApply: ((value: unknown) => void) | null = null;
    const pendingApply = new Promise((resolve) => {
      resolveApply = resolve;
    });
    vi.mocked(applyPhaseCorrection).mockReturnValue(pendingApply as Promise<never>);
    vi.mocked(fetchRun).mockResolvedValue(buildRun());

    render(<RunInitiationForm />);

    fireEvent.change(screen.getByPlaceholderText(/Enter free-text API specification/i), {
      target: { value: 'Create todo api' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Initiate BMAD Run/i }));

    const applyButton = await screen.findByRole('button', { name: /Apply correction/i });
    fireEvent.click(applyButton);
    expect(await screen.findByRole('button', { name: /Applying correction/i })).toBeDisabled();

    resolveApply?.({ status: 'correction-applied' });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Apply correction/i })).toBeEnabled();
    });
  });
});
