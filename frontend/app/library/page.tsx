import { Suspense } from 'react';
import HomePage from '../page';

export default function LibraryPage() {
  return (
    <Suspense fallback={null}>
      <HomePage />
    </Suspense>
  );
}
