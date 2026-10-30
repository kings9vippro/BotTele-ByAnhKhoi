// * DEV KHÔI PHAN +
// Nhà Phát Triển Chính Thức & Độc Quyền
// Bản quyền © 2026

#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

extern "C" {
    EXPORT uint8_t* build_binary_payload(const char* gid, const char* imei, int depth, int* out_len) {
        int cap = 1024 * 512; 
        uint8_t* buf = (uint8_t*)malloc(cap);
        if (!buf) return NULL;
        
        int pos = 0;
        uint32_t magic = 0x5A4C4F32; 
        memcpy(buf + pos, &magic, 4); pos += 4;
        
        uint32_t gid_len = strlen(gid);
        memcpy(buf + pos, &gid_len, 4); pos += 4;
        memcpy(buf + pos, gid, gid_len); pos += gid_len;
        
        uint32_t imei_len = strlen(imei);
        memcpy(buf + pos, &imei_len, 4); pos += 4;
        memcpy(buf + pos, imei, imei_len); pos += imei_len;
        
        uint32_t total_nodes = 0;
        int start_node_pos = pos;
        pos += 4; 
        
        srand((unsigned int)time(NULL));
        
        for (int i = 0; i < 10000; i++) {
            if (pos + 128 >= cap) break; 
            
            uint32_t node_type = rand() % 10; 
            memcpy(buf + pos, &node_type, 4); pos += 4;
            
            uint32_t offset = (uint32_t)(rand() % 0xFFFFFFFF);
            memcpy(buf + pos, &offset, 4); pos += 4;
            
            uint16_t payload_len = (uint16_t)(rand() % 64 + 32);
            memcpy(buf + pos, &payload_len, 2); pos += 2;
            
            for (int j = 0; j < payload_len; j++) {
                buf[pos++] = (uint8_t)(rand() % 256);
            }
            total_nodes++;
        }
        
        memcpy(buf + start_node_pos, &total_nodes, 4);
        
        if (pos + 4 < cap) {
            uint32_t end_magic = 0x454E4432; 
            memcpy(buf + pos, &end_magic, 4); pos += 4;
        }
        
        *out_len = pos;
        return buf;
    }

    EXPORT void free_binary_payload(uint8_t* ptr) {
        if (ptr) free(ptr);
    }
}
