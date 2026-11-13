"""Explicit one-tick publisher for development/rehearsal; uses approved bindings only."""
def main():
    from app.database import engine
    from app.migrations import require_current
    from app.services.forecast_registry import tick
    require_current(engine)
    print('Forecast stations processed:',tick())
if __name__=='__main__':main()
