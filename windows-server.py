"""Keep server startup errors visible in the Windows console."""
from pathlib import Path
import traceback
import server
if __name__=='__main__':
    try:
        server.main()
    except Exception:
        details=traceback.format_exc()
        print(details)
        target=Path(__file__).parent/'server-error.txt'
        target.write_text(details,encoding='utf-8')
        print('Error saved in',target)
        input('Press Enter to close...')
        raise SystemExit(1)
