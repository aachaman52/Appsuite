using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using UnityEngine;

namespace AachmanStudios.PyFlare.Unity
{
    internal static class BridgeIdempotencyStore
    {
        private static readonly string StoreDirectory = Path.Combine(
            Directory.GetParent(Application.dataPath).FullName,
            "Library",
            "PyFlare",
            "UnityBridge",
            "idempotency");

        internal static bool TryRead(
            string idempotencyKey,
            string requestFingerprint,
            out string responseJson,
            out bool conflict)
        {
            responseJson = null;
            conflict = false;
            var path = RecordPath(idempotencyKey);
            if (!File.Exists(path))
            {
                return false;
            }

            var record = JsonUtility.FromJson<IdempotencyRecord>(File.ReadAllText(path));
            if (record == null ||
                string.IsNullOrEmpty(record.request_fingerprint) ||
                string.IsNullOrEmpty(record.response_json))
            {
                throw new InvalidDataException("idempotency_record_invalid");
            }

            if (!BridgeSecurity.TokenEquals(
                    record.request_fingerprint,
                    requestFingerprint))
            {
                conflict = true;
                return false;
            }

            responseJson = record.response_json;
            return true;
        }

        internal static void Write(
            string idempotencyKey,
            string requestFingerprint,
            string responseJson)
        {
            Directory.CreateDirectory(StoreDirectory);
            var destination = RecordPath(idempotencyKey);
            if (File.Exists(destination))
            {
                return;
            }

            var record = new IdempotencyRecord
            {
                request_fingerprint = requestFingerprint,
                response_json = responseJson
            };
            var temporary = destination + "." + Guid.NewGuid().ToString("N") + ".tmp";
            File.WriteAllText(temporary, JsonUtility.ToJson(record));

            try
            {
                File.Move(temporary, destination);
            }
            catch (IOException)
            {
                if (!File.Exists(destination))
                {
                    throw;
                }

                File.Delete(temporary);
            }
        }

        internal static string Fingerprint(string value)
        {
            using (var sha256 = SHA256.Create())
            {
                return Hex(sha256.ComputeHash(Encoding.UTF8.GetBytes(value)));
            }
        }

        private static string RecordPath(string idempotencyKey)
        {
            return Path.Combine(StoreDirectory, Fingerprint(idempotencyKey) + ".json");
        }

        private static string Hex(byte[] bytes)
        {
            var builder = new StringBuilder(bytes.Length * 2);
            foreach (var value in bytes)
            {
                builder.Append(value.ToString("x2"));
            }

            return builder.ToString();
        }
    }
}
