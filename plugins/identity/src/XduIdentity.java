package xdu;

import com.google.gson.*;
import net.md_5.bungee.api.*;
import net.md_5.bungee.api.chat.TextComponent;
import net.md_5.bungee.api.connection.ProxiedPlayer;
import net.md_5.bungee.api.event.*;
import net.md_5.bungee.api.plugin.*;
import net.md_5.bungee.event.EventHandler;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.TimeUnit;

/** Console-owned admission; QQ is a self-declared event identifier, not authentication. */
public final class XduIdentity extends Plugin implements Listener {
    private final Gson gson = new GsonBuilder().setPrettyPrinting().create();
    private JsonObject players = new JsonObject();
    private Path identities, admissions, online;
    private JsonObject read(Path path) throws Exception {
        if (!Files.exists(path)) return new JsonObject();
        return JsonParser.parseString(Files.readString(path)).getAsJsonObject();
    }
    private void atomic(Path path, JsonObject value) throws Exception {
        Path temp = path.resolveSibling(path.getFileName() + ".tmp");
        Files.writeString(temp, gson.toJson(value), StandardCharsets.UTF_8);
        Files.move(temp, path, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
    }
    private synchronized void save() throws Exception {
        JsonObject root = new JsonObject(); root.addProperty("schema_version", 1); root.add("players", players);
        atomic(identities, root);
    }
    private JsonObject entry(ProxiedPlayer player) { return players.getAsJsonObject(player.getUniqueId().toString()); }
    private static void tell(CommandSender target, String message) { target.sendMessage(TextComponent.fromLegacyText(message)); }
    private JsonObject policy() {
        try { return read(admissions); } catch (Exception error) { return new JsonObject(); }
    }
    private JsonObject admins() {
        JsonObject p = policy(); return p.has("admins") ? p.getAsJsonObject("admins") : new JsonObject();
    }
    private boolean admin(ProxiedPlayer p) { return admins().has(p.getUniqueId().toString()); }
    private boolean canEnter(ProxiedPlayer p, String server) {
        if (server.equals("lobby")) return true;
        JsonObject policy = policy();
        if (!server.matches("race-[abc]") || !policy.has("active") || !policy.get("active").getAsBoolean()) return false;
        if (admin(p)) return policy.has("servers") && policy.getAsJsonArray("servers").contains(new JsonPrimitive(server));
        JsonObject own = entry(p);
        JsonObject members = policy.has("members") ? policy.getAsJsonObject("members") : new JsonObject();
        String uuid = p.getUniqueId().toString();
        return own != null && own.has("qq") && members.has(uuid) && members.get(uuid).getAsString().equals(server);
    }
    @Override public void onEnable() {
        try {
            getDataFolder().mkdirs(); identities = getDataFolder().toPath().resolve("identities.json");
            admissions = getDataFolder().toPath().resolve("admissions.json"); online = getDataFolder().toPath().resolve("online.json");
            JsonObject root = read(identities); if (root.has("players")) players = root.getAsJsonObject("players");
            Set<String> seen = new HashSet<>();
            for (Map.Entry<String, JsonElement> e : players.entrySet()) {
                UUID.fromString(e.getKey()); String qq = e.getValue().getAsJsonObject().get("qq").getAsString();
                if (!qq.matches("[1-9][0-9]{4,11}") || !seen.add(qq)) throw new IllegalStateException("Invalid identity registry");
            }
            getProxy().getPluginManager().registerListener(this, this);
            getProxy().getPluginManager().registerCommand(this, new Command("qq") {
                @Override public void execute(CommandSender sender, String[] args) {
                    if (!(sender instanceof ProxiedPlayer)) return;
                    ProxiedPlayer p = (ProxiedPlayer)sender;
                    synchronized (XduIdentity.this) {
                        JsonObject existing = entry(p);
                        if (existing != null) { tell(p, "QQ已绑定；如填错请联系现场管理员。请勿在公共聊天发送QQ。"); return; }
                        if (p.getServer() == null || !p.getServer().getInfo().getName().equals("lobby")) { tell(p, "请返回主大厅登记。"); return; }
                        if (args.length != 1 || !args[0].matches("[1-9][0-9]{4,11}")) { tell(p, "请私密输入 /qq 签到QQ号（5–12位数字，不含空格）。"); return; }
                        for (JsonElement value : players.asMap().values()) if (value.getAsJsonObject().get("qq").getAsString().equals(args[0])) {
                            tell(p, "该QQ已被其他账号绑定，请联系现场管理员核验。"); return;
                        }
                        JsonObject value = new JsonObject(); value.addProperty("qq", args[0]); value.addProperty("name", p.getName());
                        players.add(p.getUniqueId().toString(), value);
                        try { save(); tell(p, "登记成功，请在主大厅等候开赛。"); }
                        catch (Exception error) { players.remove(p.getUniqueId().toString()); tell(p, "登记保存失败，请联系管理员。"); }
                    }
                }
            });
            getProxy().getPluginManager().registerCommand(this, new Command("gpstart") {
                @Override public void execute(CommandSender sender, String[] args) {
                    if (!(sender instanceof ProxiedPlayer) || !admin((ProxiedPlayer)sender)) {
                        tell(sender, "仅现场管理员可开赛。"); return;
                    }
                    if (args.length != 0) { tell(sender, "/gpstart"); return; }
                    ProxiedPlayer p = (ProxiedPlayer)sender;
                    if (p.getServer() == null || !p.getServer().getInfo().getName().equals("lobby")) {
                        tell(sender, "请回到主大厅确认设置后再开赛。"); return;
                    }
                    JsonObject request = new JsonObject(); request.addProperty("request_id", UUID.randomUUID().toString());
                    request.addProperty("requested_by", p.getUniqueId().toString()); request.addProperty("at", System.currentTimeMillis());
                    try { atomic(getDataFolder().toPath().resolve("start-request.json"), request); tell(sender, "已请求按主大厅设置开赛；请等待服务端确认。"); }
                    catch (Exception e) { tell(sender, "无法提交开赛请求，请联系主机管理员。"); }
                }
            });
            getProxy().getPluginManager().registerCommand(this, new Command("watch") {
                @Override public void execute(CommandSender sender, String[] args) {
                    if (!(sender instanceof ProxiedPlayer)) return;
                    ProxiedPlayer p = (ProxiedPlayer)sender;
                    if (!admin(p)) { tell(p, "仅现场授予解说身份的管理员可使用。"); return; }
                    if (args.length != 1 || !args[0].matches("(?i)[abc]|lobby")) { tell(p, "/watch A|B|C|lobby"); return; }
                    String target = args[0].equalsIgnoreCase("lobby") ? "lobby" : "race-" + args[0].toLowerCase(Locale.ROOT);
                    if (!canEnter(p, target)) { tell(p, "该赛道当前未开放。"); return; }
                    p.connect(getProxy().getServerInfo(target));
                }
            });
            getProxy().getPluginManager().registerCommand(this, new Command("xduidentity") {
                @Override public void execute(CommandSender sender, String[] args) {
                    if (sender instanceof ProxiedPlayer) { tell(sender, "Console only"); return; }
                    if (args.length != 2 || !args[0].equals("reset")) { tell(sender, "xduidentity reset <uuid>; disconnect player and finish GP first"); return; }
                    try {
                        UUID id = UUID.fromString(args[1]); JsonObject p = policy();
                        if (getProxy().getPlayer(id) != null || (p.has("active") && p.get("active").getAsBoolean())) throw new IllegalStateException();
                        JsonElement old = players.remove(id.toString());
                        try { save(); } catch (Exception e) { if (old != null) players.add(id.toString(), old); throw e; }
                        tell(sender, "Identity reset");
                    } catch (Exception e) { tell(sender, "Refused: invalid UUID, connected player, active GP, or storage failure"); }
                }
            });
            getProxy().getScheduler().schedule(this, this::publishOnline, 0, 1, TimeUnit.SECONDS);
        } catch (Exception e) { throw new IllegalStateException("QQ gate failed to initialize; do not admit players", e); }
    }
    private synchronized void publishOnline() {
        JsonObject root = new JsonObject(); root.addProperty("at", System.currentTimeMillis()); JsonObject current = new JsonObject();
        for (ProxiedPlayer p : getProxy().getPlayers()) {
            JsonObject row = new JsonObject(); row.addProperty("name", p.getName()); row.addProperty("server", p.getServer() == null ? "" : p.getServer().getInfo().getName());
            current.add(p.getUniqueId().toString(), row);
        }
        root.add("players", current);
        try { atomic(online, root); } catch (Exception e) { getLogger().warning("Cannot publish admission state"); }
    }
    @EventHandler public synchronized void connected(PostLoginEvent event) {
        ProxiedPlayer p = event.getPlayer(); JsonObject row = entry(p);
        if (row != null && !p.getName().equals(row.get("name").getAsString())) {
            row.addProperty("name", p.getName()); try { save(); } catch (Exception e) { p.disconnect(TextComponent.fromLegacyText("身份保存失败，请联系管理员")); }
        }
        tell(p, row == null ? "参赛前必须输入 /qq 签到QQ号。QQ仅作现场身份关联，不会公开显示。" : "欢迎回来，请在主大厅等候。");
    }
    @EventHandler public void connecting(ServerConnectEvent event) {
        ProxiedPlayer p = event.getPlayer();
        if (event.getReason() == ServerConnectEvent.Reason.JOIN_PROXY) { event.setTarget(getProxy().getServerInfo("lobby")); return; }
        if (!canEnter(p, event.getTarget().getName())) {
            event.setCancelled(true); tell(p, "比赛服未开放或你不在本次名册；请在主大厅登记QQ并等候开赛。");
        }
    }
}
