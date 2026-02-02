import { useEffect, useRef, useState, forwardRef, useImperativeHandle } from 'react';
import DiceBox from '@3d-dice/dice-box';

const DiceRoller = forwardRef(({ onRollComplete }, ref) => {
  const diceBoxRef = useRef(null);
  const containerRef = useRef(null);
  const [isInitialized, setIsInitialized] = useState(false);
  const [isRolling, setIsRolling] = useState(false);

  useEffect(() => {
    if (isInitialized || !containerRef.current) return;

    console.log('[DiceRoller] Starting initialization...');

    // Initialize dice box with new v1.1.0 API (single config object)
    const diceBox = new DiceBox({
      id: 'dice-canvas',
      assetPath: '/assets/',
      theme: 'default',
      scale: 6,
      gravity: 2,
      mass: 1,
      friction: 0.8,
      restitution: 0.5,
      linearDamping: 0.5,
      angularDamping: 0.4,
      spinForce: 6,
      throwForce: 5,
      startingHeight: 10,
      settleTimeout: 2500,
      offscreen: false,
      delay: 10,
    });

    diceBox.init().then(() => {
      diceBoxRef.current = diceBox;
      setIsInitialized(true);
      console.log('[DiceRoller] ✓ Initialized successfully');
    }).catch(err => {
      console.error('[DiceRoller] ✗ Failed to initialize:', err);
      setIsInitialized(false);
    });

    // Cleanup on unmount
    return () => {
      if (diceBoxRef.current) {
        diceBoxRef.current.clear();
      }
    };
  }, []);

  // Method to roll dice with specific values
  const roll = async (die1, die2) => {
    console.log(`[DiceRoller] roll() called with values: ${die1}, ${die2}`);
    console.log(`[DiceRoller] isInitialized: ${isInitialized}, diceBoxRef.current:`, diceBoxRef.current);

    if (!diceBoxRef.current || !isInitialized) {
      console.warn('[DiceRoller] ⚠ DiceBox not initialized, skipping animation');
      if (onRollComplete) {
        onRollComplete(die1, die2);
      }
      return;
    }

    setIsRolling(true);
    console.log('[DiceRoller] Starting dice roll animation...');

    try {
      // Clear any previous dice
      diceBoxRef.current.clear();

      // Roll two dice with specific values
      const result = await diceBoxRef.current.roll([
        { qty: 1, sides: 6, value: die1 },
        { qty: 1, sides: 6, value: die2 }
      ]);

      console.log('[DiceRoller] Dice roll initiated, result:', result);

      // Wait for dice to settle before notifying completion
      setTimeout(() => {
        console.log('[DiceRoller] Dice settled');
        setIsRolling(false);
        if (onRollComplete) {
          onRollComplete(die1, die2);
        }
        // Clear dice after a brief display
        setTimeout(() => {
          if (diceBoxRef.current) {
            console.log('[DiceRoller] Clearing dice');
            diceBoxRef.current.clear();
          }
        }, 1500);
      }, 2500);
    } catch (error) {
      console.error('[DiceRoller] ✗ Error rolling dice:', error);
      setIsRolling(false);
      // Fallback if animation fails
      if (onRollComplete) {
        onRollComplete(die1, die2);
      }
    }
  };

  // Expose roll method to parent via ref
  useImperativeHandle(ref, () => ({
    roll,
    isInitialized,
    isRolling
  }));

  return (
    <div
      ref={containerRef}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: isRolling ? 1000 : -1,
        opacity: isRolling ? 1 : 0,
        transition: 'opacity 0.3s ease'
      }}
    >
      <canvas
        id="dice-canvas"
        style={{
          width: '100%',
          height: '100%'
        }}
      />
    </div>
  );
});

DiceRoller.displayName = 'DiceRoller';

export default DiceRoller;
