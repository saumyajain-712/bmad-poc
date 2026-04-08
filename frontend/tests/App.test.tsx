import { render, screen } from '@testing-library/react';
import App from '../src/App';

describe('App', () => {
  it('should render the BMAD Run Initiator title', () => {
    render(<App />);
    expect(screen.getByText(/BMAD Run Initiator/i)).toBeDefined();
  });
});