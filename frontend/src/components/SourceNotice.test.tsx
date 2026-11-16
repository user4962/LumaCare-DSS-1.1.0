import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SourceNotice } from './ui'

describe('SourceNotice', () => {
  it('explicitly labels synthetic fallback records', () => {
    render(<SourceNotice source="demo" error="Research data service unavailable." />)
    expect(screen.getByText('Synthetic demo data')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Research data service unavailable.')
  })

  it('stays absent when the connected API is healthy', () => {
    const { container } = render(<SourceNotice source="api" error={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})
