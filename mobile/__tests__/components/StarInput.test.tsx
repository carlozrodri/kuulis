import { describe, expect, it, jest } from '@jest/globals';
import { fireEvent, screen } from '@testing-library/react-native';

import { StarInput } from '@/features/ride/components';
import i18n from '@/i18n';

import { renderScreen } from '../../test-utils/render';

describe('StarInput', () => {
  it('is a radio group: screen readers hear which star is chosen', async () => {
    void i18n.changeLanguage('es');
    const onChange = jest.fn();
    await renderScreen(<StarInput value={4} onChange={onChange} />);

    const stars = screen.getAllByRole('radio');
    expect(stars).toHaveLength(5);
    expect(stars.map((star) => star.props.accessibilityState?.checked)).toEqual([false, false, false, true, false]);

    await fireEvent.press(screen.getByLabelText(i18n.t('rating.starN', { count: 2 })));
    expect(onChange).toHaveBeenCalledWith(2);
  });
});
