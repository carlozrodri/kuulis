import { DriverHome } from '@/features/driver/DriverHome';
import { PassengerHome } from '@/features/passenger/PassengerHome';
import { useMode } from '@/providers/ModeProvider';

export default function HomeScreen() {
  const { mode } = useMode();
  return mode === 'driver' ? <DriverHome /> : <PassengerHome />;
}
