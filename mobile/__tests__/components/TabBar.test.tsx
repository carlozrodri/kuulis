import { afterEach, describe, expect, it, jest } from '@jest/globals';
import { cleanup, fireEvent, screen } from '@testing-library/react-native';
import type { BottomTabBarProps } from 'expo-router/tabs';

import { TabBar } from '@/components/TabBar';

import { renderScreen } from '../../test-utils/render';

/** The props Expo Router 58 gives a custom `tabBar`: `emitter` and `navigateToTab` instead of `navigation`. */
function props(defaultPrevented = false) {
  const names = ['index', 'rides', 'wallet', 'notifications', 'profile'];
  const routes = names.map((name) => ({ key: `${name}-key`, name, params: undefined }));
  const descriptors = Object.fromEntries(
    routes.map((route) => [route.key, { options: { title: route.name, hidden: route.name === 'wallet' } }]),
  );
  const emit = jest.fn((_event: object) => ({ defaultPrevented }));
  const navigateToTab = jest.fn();
  const tabProps = { state: { index: 0, routes }, descriptors, emitter: { emit }, navigateToTab, insets: { top: 0, right: 0, bottom: 0, left: 0 } };
  return { tabProps: tabProps as unknown as BottomTabBarProps, emit, navigateToTab };
}

describe('tab bar', () => {
  afterEach(cleanup);

  it('opens another tab through navigateToTab', async () => {
    const { tabProps, emit, navigateToTab } = props();
    await renderScreen(<TabBar {...tabProps} />);
    await fireEvent.press(screen.getByLabelText('rides'));
    expect(emit).toHaveBeenCalledWith({ type: 'tabPress', target: 'rides-key', canPreventDefault: true });
    expect(navigateToTab).toHaveBeenCalledWith('rides-key');
  });

  it('does not navigate when the focused tab is pressed or the press is prevented', async () => {
    const { tabProps, navigateToTab } = props(true);
    await renderScreen(<TabBar {...tabProps} />);
    await fireEvent.press(screen.getByLabelText('index'));
    await fireEvent.press(screen.getByLabelText('rides'));
    expect(navigateToTab).not.toHaveBeenCalled();
  });

  it('hides the tabs declared with href: null', async () => {
    const { tabProps } = props();
    await renderScreen(<TabBar {...tabProps} />);
    expect(screen.queryByLabelText('wallet')).toBeNull();
    for (const name of ['index', 'rides', 'notifications', 'profile']) expect(screen.getByLabelText(name)).toBeTruthy();
  });
});
