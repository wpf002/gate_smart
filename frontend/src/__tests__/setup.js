import '@testing-library/jest-dom';

// Silence "not wrapped in act()" noise from async Zustand updates
global.IS_REACT_ACT_ENVIRONMENT = true;
