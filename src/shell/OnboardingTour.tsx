import { useEffect, useRef } from 'react';
import { driver } from 'driver.js';
import 'driver.js/dist/driver.css';
import { useTourStore } from '../store/tourStore';
import { useUIStore } from '../store/uiStore';
import { TOUR_STEPS } from '../content/onboarding/tour_steps';

export const OnboardingTour: React.FC = () => {
  const { tourActive, checkFirstLaunch, endTour } = useTourStore();
  const setActiveView = useUIStore((state) => state.setActiveView);
  const setSelectedCompound = useUIStore((state) => state.setSelectedCompound);
  const driverRef = useRef<any>(null);

  useEffect(() => {
    // Check if this is the first launch of the application
    checkFirstLaunch();
  }, [checkFirstLaunch]);

  useEffect(() => {
    if (!tourActive) {
      if (driverRef.current) {
        driverRef.current.destroy();
        driverRef.current = null;
      }
      return;
    }

    // Initialize driver.js
    const driverObj = driver({
      showProgress: true,
      allowClose: true,
      overlayColor: 'rgba(0, 0, 0, 0.65)',
      steps: TOUR_STEPS.map((step) => {
        return {
          element: step.targetElement,
          popover: {
            title: step.title,
            description: step.body,
            side: 'bottom',
            align: 'start',
            nextBtnText: step.nextLabel || 'Next',
            prevBtnText: 'Back',
            doneBtnText: 'Finish',
          },
        };
      }),
      onCloseClick: () => {
        endTour();
      },
      onDestroyed: () => {
        endTour();
      },
      // Capture step changes to trigger navigation or loading demo compounds
      onHighlightStarted: (_element, _step, options) => {
        const stepIndex = options?.state?.activeIndex;
        if (stepIndex === undefined) return;
        const currentStep = TOUR_STEPS[stepIndex];

        if (currentStep && currentStep.action) {
          const action = currentStep.action;
          if (action.type === 'navigate') {
            const targetView = action.view === 'docking' ? 'viewer3d' : action.view;
            setActiveView(targetView as any);
          } else if (action.type === 'load_demo_compound') {
            // Set imidacloprid or similar demo compound
            setSelectedCompound('c1');
          }
        }
      }
    });

    driverRef.current = driverObj;
    
    // Give a short delay to make sure the app elements are fully loaded
    const timer = setTimeout(() => {
      driverObj.drive();
    }, 500);

    return () => {
      clearTimeout(timer);
      if (driverRef.current) {
        driverRef.current.destroy();
      }
    };
  }, [tourActive, setActiveView, setSelectedCompound, endTour]);

  return null;
};
