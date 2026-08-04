import sys
from pathlib import Path

# Thêm đường dẫn project vào sys.path để có thể import từ src
PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))

try:
    from src.task9_retrieval_pipeline import retrieve
except ImportError as e:
    print(f"Lỗi import: {e}")
    print("Vui lòng đảm bảo Role 2 đã hoàn thiện Task 9 (hàm retrieve) trước khi chạy script này!")
    sys.exit(1)

def main():
    print("=" * 60)
    print("  CLI KIỂM THỬ FALLBACK - DỰ ÁN TRỢ LÝ LUẬT LAO ĐỘNG")
    print("=" * 60)
    print("Nhập các câu hỏi ngoài domain (OOD) để kiểm tra xem hệ")
    print("thống có tự động fallback sang PageIndex hay không.")
    print("Gõ 'exit' hoặc 'quit' để thoát chương trình.\n")

    while True:
        try:
            query = input("\n👉 Nhập câu hỏi của bạn: ").strip()
            if query.lower() in ['exit', 'quit']:
                print("Đang thoát...")
                break
            
            if not query:
                continue

            print("-" * 60)
            print("Đang truy vấn...")
            
            # Cố gắng bắt lỗi NotImplementedError nếu Role 2 chưa code xong
            try:
                # Top_k = 3 để dễ nhìn kết quả
                results = retrieve(query, top_k=3)
                
                if not results:
                    print("⚠️ Hệ thống trả về mảng rỗng (Không tìm thấy gì, kể cả fallback).")
                else:
                    for i, r in enumerate(results, 1):
                        source = r.get('source', 'N/A')
                        score = r.get('score', 0.0)
                        content = r.get('content', '')[:100].replace('\n', ' ')
                        print(f"  {i}. [{score:.3f}] [Nguồn: {source}] {content}...")
                        
            except NotImplementedError:
                print("❌ LỖI: Hàm `retrieve` trong Task 9 chưa được cài đặt (NotImplementedError).")
                print("Bạn hãy hối thúc Role 2 hoàn thiện code đi nhé!")
            except Exception as e:
                print(f"❌ Lỗi hệ thống khi chạy retrieve: {e}")
                
        except KeyboardInterrupt:
            print("\nĐang thoát...")
            break

if __name__ == "__main__":
    main()
